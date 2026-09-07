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
    start_time: float,
    end_time: Optional[float] = None,
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global",
    model_name: str = "gemini-3.8-flash"
) -> float:
    """
    Samples frames across the clip and uses Gemini 3.8 Flash multimodal vision
    with 2D bounding-box spatial grounding to detect the exact horizontal center
    of the primary human speaker.
    Returns a float ratio between 0.05 and 0.95 (default 0.5 if undetected).
    """
    if end_time is None or end_time <= start_time:
        sample_times = [start_time]
    else:
        duration = end_time - start_time
        # Sample at 30% and 70% of clip duration
        sample_times = [
            start_time + duration * 0.30,
            start_time + duration * 0.70
        ]

    temp_dir = Path("output/_temp_frames")
    temp_dir.mkdir(parents=True, exist_ok=True)

    credentials_path = Path("config/gcp_service_account_key.json")
    if credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path.resolve())

    from google import genai
    from PIL import Image

    client = None
    try:
        client = genai.Client(vertexai=True, project=project_id, location=location)
    except Exception as e:
        print(f"   [AI Centering Warning] Could not initialize Gemini client: {e}")
        return 0.5

    prompt = (
        "Detect the primary human speaker standing on stage in this video frame.\n"
        "Ignore slides, projector screens, background banners, and audience.\n"
        "Return the 2D bounding box [ymin, xmin, ymax, xmax] of the speaker normalized on a scale of 0 to 1000.\n"
        "Output JSON:\n"
        "{\n"
        '  "speaker_found": true,\n'
        '  "box_2d": [ymin, xmin, ymax, xmax]\n'
        "}"
    )

    detected_centers = []

    for ts in sample_times:
        temp_frame = temp_dir / f"ref_{abs(hash(source_video)) % 10000}_{int(ts * 100)}.jpg"
        try:
            cmd_frame = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", source_video,
                "-vframes", "1",
                "-update", "1",
                "-q:v", "2",
                str(temp_frame)
            ]
            subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            if not temp_frame.exists():
                continue

            img = Image.open(temp_frame)
            res = client.models.generate_content(
                model=model_name,
                contents=[img, prompt],
                config={"response_mime_type": "application/json"}
            )
            data = json.loads(res.text)
            if data.get("speaker_found") and "box_2d" in data:
                box = data["box_2d"]
                if len(box) == 4:
                    # box is [ymin, xmin, ymax, xmax] in 0-1000 scale
                    center_ratio = (float(box[1]) + float(box[3])) / 2000.0
                    if 0.05 <= center_ratio <= 0.95:
                        detected_centers.append(center_ratio)
        except Exception:
            pass
        finally:
            if temp_frame.exists():
                try:
                    temp_frame.unlink()
                except Exception:
                    pass

    if detected_centers:
        final_ratio = round(sum(detected_centers) / len(detected_centers), 3)
        print(f"   🎯 [AI Smart Centering] Speaker detected at horizontal center = {final_ratio:.3f}")
        return final_ratio

    print("   ℹ️ [AI Smart Centering] Speaker not detected or center default used (0.500)")
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
        speaker_center_ratio = detect_speaker_center_ratio(
            source_video=source_video,
            start_time=start_time,
            end_time=end_time
        )

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
