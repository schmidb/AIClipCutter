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
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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
    banner_fade_seconds: float = 3.5,
    ass_path: Optional[str] = None,
    generate_cover: bool = True
) -> bool:
    """
    Renders a 9:16 vertical video clip from source video using FFmpeg.
    - AI Smart Centering (speaker dynamically tracked and centered)
    - 3.5s smooth fade-out hook headline banner
    - Burned-in ASS dynamic subtitles in Instagram safe zone
    - Broadcast-standard -14 LUFS audio normalization + 0.4s clean outro fade
    - Dedicated 1080x1920 cover image export (cover_*.jpg)
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

    # 4. Burn-in ASS dynamic subtitles if provided
    if ass_path and os.path.exists(ass_path):
        ass_filter_path = Path(ass_path).as_posix()
        filter_complex += f",ass={ass_filter_path}"

    duration = max(0.5, end_time - start_time)

    # 5. Broadcast Audio Processing: Stage Rumble Cut (80Hz) + -14 LUFS Loudness + 0.4s Smooth Outro Fade
    fade_start = max(0.1, duration - 0.4)
    audio_filter = f"highpass=f=80,loudnorm=I=-14:LRA=11:TP=-1.5,afade=t=out:st={fade_start:.2f}:d=0.4"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_time),
        "-i", source_video,
        "-t", str(duration),
        "-vf", filter_complex,
        "-af", audio_filter,
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
            
            # 6. Dedicated High-Res Cover Thumbnail Generation
            if generate_cover:
                out_p = Path(output_path)
                cover_name = out_p.stem.replace("clip_", "cover_") + ".jpg"
                cover_path = str(out_p.parent / cover_name)
                thumb_time = min(1.0, duration / 2.0)
                thumb_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(thumb_time),
                    "-i", output_path,
                    "-frames:v", "1",
                    "-update", "1",
                    "-q:v", "2",
                    cover_path
                ]
                subprocess.run(thumb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(cover_path):
                    print(f"      📸 Exported Reel Cover: {cover_name}")

            return True
        else:
            print(f"   ❌ FFmpeg render error for {output_path}: {res.stderr.decode('utf-8', errors='ignore')[-300:]}")
            return False
    except Exception as e:
        print(f"   ❌ Error executing FFmpeg: {e}")
        return False
