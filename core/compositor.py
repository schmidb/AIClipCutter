"""
AIClipCutter Video Compositor.
Cuts and renders 9:16 vertical clips from source videos using FFmpeg.
Applies:
- AI Smart Centering (Gemini 3.8 Flash multimodal vision detects speaker position)
- High-precision timestamp cutting
- 9:16 vertical framing centered on the active human speaker
- Top hook banner headline overlay
- Clean audio sync
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


def detect_speaker_center_ratio(
    source_video: str,
    timestamp: float,
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global",
    model_name: str = "gemini-3.8-flash"
) -> float:
    """
    Extracts a reference frame at the given timestamp and uses Gemini 3.8 Flash
    multimodal vision to find the horizontal center ratio (0.0 to 1.0) of the primary human speaker.
    Falls back to 0.5 (center) if detection fails or speaker is not visible.
    """
    temp_dir = Path("output/_temp_frames")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_frame = temp_dir / f"ref_{abs(hash(source_video)) % 10000}_{int(timestamp)}.jpg"

    try:
        cmd_frame = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", source_video,
            "-vframes", "1",
            "-q:v", "2",
            str(temp_frame)
        ]
        subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        if not temp_frame.exists():
            return 0.5

        credentials_path = Path("config/gcp_service_account_key.json")
        if credentials_path.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path.resolve())

        from google import genai
        from PIL import Image

        client = genai.Client(vertexai=True, project=project_id, location=location)
        img = Image.open(temp_frame)

        prompt = (
            "Identify the human speaker standing on stage in this video frame.\n"
            "Ignore slides, projector screens, banners, or logos.\n"
            "Return a JSON object:\n"
            "{\n"
            '  "speaker_found": true,\n'
            '  "speaker_center_x_ratio": <float between 0.0 and 1.0>\n'
            "}"
        )

        res = client.models.generate_content(
            model=model_name,
            contents=[img, prompt],
            config={"response_mime_type": "application/json"}
        )
        data = json.loads(res.text)
        if data.get("speaker_found") and "speaker_center_x_ratio" in data:
            ratio = float(data["speaker_center_x_ratio"])
            if 0.05 <= ratio <= 0.95:
                return ratio
    except Exception as e:
        print(f"   [AI Centering Warning] Could not detect speaker at {timestamp:.1f}s ({e}), using default center.")
    finally:
        if temp_frame.exists():
            try:
                temp_frame.unlink()
            except Exception:
                pass

    return 0.5


def render_vertical_clip(
    source_video: str,
    start_time: float,
    end_time: float,
    output_path: str,
    hook_banner: str = "",
    target_width: int = 1080,
    target_height: int = 1920,
    speaker_center_ratio: Optional[float] = None,
    enable_ai_centering: bool = True,
    banner_fade_seconds: float = 3.5
) -> bool:
    """
    Renders a 9:16 vertical video clip from source video using FFmpeg.
    If enable_ai_centering is True, dynamically centers the vertical crop on the speaker.
    Hook banner headlines appear prominently for the first 3 seconds, then smoothly fade out by 3.5s.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # 1. AI Smart Centering
    if enable_ai_centering and speaker_center_ratio is None:
        sample_time = start_time + min(2.0, (end_time - start_time) / 2.0)
        speaker_center_ratio = detect_speaker_center_ratio(source_video, sample_time)

    if speaker_center_ratio is None:
        speaker_center_ratio = 0.5

    # 2. Clean hook text for FFmpeg drawtext
    clean_hook = hook_banner.replace("'", "").replace(":", " -").replace('"', "").strip()
    if len(clean_hook) > 45:
        words = clean_hook.split()
        mid = len(words) // 2
        clean_hook = " ".join(words[:mid]) + "\\n" + " ".join(words[mid:])

    # 3. Dynamic Crop Expression (Centers on speaker horizontally without overflowing bounds)
    ratio_str = f"{speaker_center_ratio:.4f}"
    crop_filter = f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*{ratio_str}-ih*9/32))':0"
    filter_complex = f"{crop_filter},scale={target_width}:{target_height}"

    if clean_hook:
        if banner_fade_seconds and banner_fade_seconds > 0:
            fade_start = max(0.5, banner_fade_seconds - 0.5)
            fade_expr = f":enable='lte(t,{banner_fade_seconds})':alpha='if(lt(t,{fade_start}),1.0,1.0-(t-{fade_start})/0.5)'"
        else:
            fade_expr = ""
        drawtext = (
            f"drawtext=text='{clean_hook}':"
            f"fontsize=46:fontcolor=white:"
            f"box=1:boxcolor=black@0.65:boxborderw=18:"
            f"line_spacing=12:"
            f"x=(w-text_w)/2:y=240"
            f"{fade_expr}"
        )
        filter_complex += f",{drawtext}"

    duration = max(0.5, end_time - start_time)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_time),
        "-i", source_video,
        "-t", str(duration),
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(output_path):
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"   ✅ Rendered: {os.path.basename(output_path)} ({duration:.1f}s, {file_size_mb:.2f} MB, speaker_x={speaker_center_ratio:.2f})")
            return True
        else:
            print(f"   ❌ FFmpeg render error for {output_path}: {res.stderr.decode('utf-8', errors='ignore')[-300:]}")
            return False
    except Exception as e:
        print(f"   ❌ Error executing FFmpeg: {e}")
        return False
