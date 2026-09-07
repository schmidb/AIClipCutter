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
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple


def detect_speaker_framing_trajectory(
    source_video: str,
    start_time: float,
    end_time: Optional[float] = None,
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global",
    model_name: str = "gemini-3.8-flash"
) -> List[Tuple[float, float]]:
    """
    Samples multiple keyframes across the clip and uses Gemini 3.8 Flash multimodal vision
    in a single batched call with 2D bounding-box spatial grounding to detect the horizontal
    trajectory of the primary human speaker.
    Returns a list of (time_offset, center_ratio) tuples.
    """
    if end_time is None or end_time <= start_time:
        duration = 3.0
    else:
        duration = max(1.0, end_time - start_time)

    # Sample keyframe timestamps across the clip duration (every ~2.5 - 3.0s, 3 to 7 samples)
    if duration <= 4.0:
        offsets = [round(duration * 0.5, 2)]
    else:
        step = 2.5 if duration <= 15.0 else 3.0
        offsets = [round(i * step, 2) for i in range(int(duration / step) + 1)]
        if offsets[0] > 0.5:
            offsets.insert(0, 0.5)
        if (duration - offsets[-1]) > 1.2:
            offsets.append(round(duration - 0.5, 2))

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
        return [(0.0, 0.5)]

    contents = []
    temp_files = []
    extracted_offsets = []

    try:
        for idx, off in enumerate(offsets):
            ts = start_time + off
            temp_frame = temp_dir / f"ref_{abs(hash(source_video)) % 10000}_{idx}_{int(ts * 100)}.jpg"
            cmd_frame = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", source_video,
                "-vframes", "1",
                "-update", "1",
                "-q:v", "3",
                str(temp_frame)
            ]
            subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if temp_frame.exists():
                temp_files.append(temp_frame)
                img = Image.open(temp_frame)
                contents.append(f"Frame #{idx} (time offset {off:.1f}s):")
                contents.append(img)
                extracted_offsets.append(off)

        if not contents:
            return [(0.0, 0.5)]

        prompt = (
            "Analyze the sequence of video frames from a stage presentation.\n"
            "For each frame:\n"
            "1. Detect the primary human speaker standing on stage.\n"
            "2. Return the speaker's 2D bounding box [ymin, xmin, ymax, xmax] (normalized 0-1000 scale).\n"
            "Ignore projector screens, slides, and audience.\n\n"
            "Output JSON format:\n"
            "{\n"
            '  "frames": [\n'
            '    {"frame_index": 0, "speaker_found": true, "box_2d": [ymin, xmin, ymax, xmax]},\n'
            "    ...\n"
            "  ]\n"
            "}"
        )
        contents.append(prompt)

        res = client.models.generate_content(
            model=model_name,
            contents=contents,
            config={"response_mime_type": "application/json"}
        )
        raw_text = res.text.strip()
        try:
            data = json.loads(raw_text, strict=False)
        except Exception:
            clean_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', raw_text)
            data = json.loads(clean_json)
        frames_data = data.get("frames", [])
        if isinstance(frames_data, list):
            for item in frames_data:
                f_idx = item.get("frame_index")
                if f_idx is not None and f_idx < len(extracted_offsets) and item.get("speaker_found") and "box_2d" in item:
                    box = item["box_2d"]
                    if len(box) == 4:
                        cx = (float(box[1]) + float(box[3])) / 2000.0
                        cx = max(0.15, min(0.85, cx))
                        trajectory.append((extracted_offsets[f_idx], cx))

        if trajectory:
            return trajectory

    except Exception as e:
        print(f"   [AI Centering Warning] Trajectory tracking error: {e}")
    finally:
        for tf in temp_files:
            if tf.exists():
                try:
                    tf.unlink()
                except Exception:
                    pass

    return [(0.0, 0.5)]


def build_cinematic_crop_filter(
    samples: List[Tuple[float, float]],
    duration: float,
    target_width: int = 1080,
    target_height: int = 1920
) -> str:
    """
    Constructs an intelligent, smooth FFmpeg crop and scale filter from speaker trajectory points.
    - Deadzone tolerance (if movement <= 0.08, stays 100% static)
    - Minimum hold duration (>= 3.2s) ensures at most 1 or 2 framing changes per clip
    - Instant cut on camera shot switches
    - Smoothstep easing (3p^2 - 2p^3) when speaker walks across stage
    """
    if not samples:
        return f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*0.5000-ih*9/32))':0,scale={target_width}:{target_height}"

    raw_points = [(float(t), max(0.15, min(0.85, float(c)))) for t, c in samples]
    raw_points.sort(key=lambda p: p[0])
    centers = [c for _, c in raw_points]

    # Deadzone tolerance: if variation is small (<= 0.08), lock steady static framing
    if max(centers) - min(centers) <= 0.08:
        avg_c = round(sum(centers) / len(centers), 4)
        print(f"   🎯 [Auto-Framing] Speaker steady: static framing at center = {avg_c:.3f}")
        return f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*{avg_c:.4f}-ih*9/32))':0,scale={target_width}:{target_height}"

    min_hold = 3.2

    # Find the single most significant split point
    best_split = None
    best_var_reduction = 0
    total_var = sum((c - sum(centers)/len(centers))**2 for c in centers)

    for i in range(1, len(raw_points)):
        t_split = (raw_points[i-1][0] + raw_points[i][0]) / 2.0
        if t_split < min_hold or (duration - t_split) < min_hold:
            continue
        left_c = [c for t, c in raw_points if t < t_split]
        right_c = [c for t, c in raw_points if t >= t_split]
        if not left_c or not right_c:
            continue
        var_left = sum((c - sum(left_c)/len(left_c))**2 for c in left_c)
        var_right = sum((c - sum(right_c)/len(right_c))**2 for c in right_c)
        reduction = total_var - (var_left + var_right)
        delta = abs(sum(left_c)/len(left_c) - sum(right_c)/len(right_c))
        if reduction > best_var_reduction and delta >= 0.08:
            best_var_reduction = reduction
            best_split = (t_split, left_c, right_c)

    if best_split is None:
        avg_c = round(sum(centers) / len(centers), 4)
        print(f"   🎯 [Auto-Framing] Single zone: center = {avg_c:.3f}")
        return f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*{avg_c:.4f}-ih*9/32))':0,scale={target_width}:{target_height}"

    t_split, left_c, right_c = best_split
    c1 = round(sum(left_c) / len(left_c), 4)
    c2 = round(sum(right_c) / len(right_c), 4)
    print(f"   🎯 [Auto-Framing] Dynamic 2-zone framing: 0.0s-{t_split:.1f}s center={c1:.3f} | {t_split:.1f}s-{duration:.1f}s center={c2:.3f}")

    # Check whether it's an instant camera shot cut or a smooth stage walk
    jump_size = abs(c2 - c1)
    if jump_size >= 0.12:
        # Camera shot cut: instant transition at t_split
        x_expr = f"if(lt(t,{t_split:.2f}),iw*{c1:.4f}-ow/2,iw*{c2:.4f}-ow/2)"
    else:
        # Smoothstep easing pan over 1.2 seconds
        pan_dur = 1.2
        pan_start = max(0.1, t_split - pan_dur / 2.0)
        pan_end = min(duration - 0.1, t_split + pan_dur / 2.0)
        dur_actual = max(0.2, round(pan_end - pan_start, 2))
        p = f"((t-{pan_start:.2f})/{dur_actual:.2f})"
        ease = f"({p}*{p}*(3-2*{p}))"
        pan_expr = f"(iw*{c1:.4f}-ow/2+(iw*{c2 - c1:.4f})*{ease})"
        x_expr = f"if(lt(t,{pan_start:.2f}),iw*{c1:.4f}-ow/2,if(lt(t,{pan_end:.2f}),{pan_expr},iw*{c2:.4f}-ow/2))"

    crop_filter = f"crop=ih*9/16:ih:'max(0,min(iw-ow,{x_expr}))':0"
    return f"{crop_filter},scale={target_width}:{target_height}"


def detect_speaker_center_ratio(
    source_video: str,
    start_time: float,
    end_time: Optional[float] = None,
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global",
    model_name: str = "gemini-3.8-flash"
) -> float:
    """
    Backwards-compatible convenience wrapper returning the primary center ratio.
    """
    trajectory = detect_speaker_framing_trajectory(
        source_video=source_video,
        start_time=start_time,
        end_time=end_time,
        project_id=project_id,
        location=location,
        model_name=model_name
    )
    if trajectory:
        centers = [c for _, c in trajectory]
        return round(sum(centers) / len(centers), 3)
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
    - Smart Multi-Point Auto-Framing (camera-cut aware, deadzone stability, smooth easing)
    - 3.5s smooth fade-out hook headline banner
    - Burned-in ASS dynamic subtitles in Instagram safe zone
    - Broadcast-standard -14 LUFS audio normalization + 0.08s micro-fade-in + 0.4s clean outro fade
    - Dedicated 1080x1920 cover image export (cover_*.jpg)
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration = max(0.5, end_time - start_time)

    # 1. AI Smart Centering & Framing
    if speaker_center_ratio is not None:
        ratio_str = f"{speaker_center_ratio:.4f}"
        crop_filter = f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*{ratio_str}-ih*9/32))':0"
        filter_complex = f"{crop_filter},scale={target_width}:{target_height}"
    elif enable_ai_centering:
        trajectory = detect_speaker_framing_trajectory(
            source_video=source_video,
            start_time=start_time,
            end_time=end_time
        )
        filter_complex = build_cinematic_crop_filter(
            samples=trajectory,
            duration=duration,
            target_width=target_width,
            target_height=target_height
        )
    else:
        crop_filter = f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*0.5000-ih*9/32))':0"
        filter_complex = f"{crop_filter},scale={target_width}:{target_height}"

    # 2. Clean hook text for FFmpeg drawtext
    clean_hook = hook_banner.replace("'", "").replace(":", " -").replace('"', "").strip()
    if len(clean_hook) > 45:
        words = clean_hook.split()
        mid = len(words) // 2
        clean_hook = " ".join(words[:mid]) + "\\n" + " ".join(words[mid:])

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

    # 5. Broadcast Audio Processing: Stage Rumble Cut (80Hz) + -14 LUFS Loudness + 0.08s Micro-Fade-In + 0.4s Smooth Outro Fade
    fade_start = max(0.1, duration - 0.4)
    audio_filter = f"highpass=f=80,loudnorm=I=-14:LRA=11:TP=-1.5,afade=t=in:st=0:d=0.08,afade=t=out:st={fade_start:.2f}:d=0.4"

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
            x_info = f", speaker_x={speaker_center_ratio:.2f}" if speaker_center_ratio is not None else ""
            print(f"   ✅ Rendered: {os.path.basename(output_path)} ({duration:.1f}s, {file_size_mb:.2f} MB{x_info})")
            
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
