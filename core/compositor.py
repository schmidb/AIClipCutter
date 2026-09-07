"""
AIClipCutter Video Compositor.
Cuts and renders 9:16 vertical clips from source videos using FFmpeg.
Applies:
- High-precision timestamp cutting
- 9:16 vertical framing (speaker center-crop)
- Top hook banner headline overlay
- Clean audio sync
"""

import os
import subprocess
from pathlib import Path


def render_vertical_clip(
    source_video: str,
    start_time: float,
    end_time: float,
    output_path: str,
    hook_banner: str = "",
    target_width: int = 1080,
    target_height: int = 1920
) -> bool:
    """
    Renders a 9:16 vertical video clip from source video using FFmpeg.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Clean hook text for FFmpeg drawtext
    clean_hook = hook_banner.replace("'", "").replace(":", " -").replace('"', "").strip()
    if len(clean_hook) > 45:
        # Wrap long hook into two lines
        words = clean_hook.split()
        mid = len(words) // 2
        clean_hook = " ".join(words[:mid]) + "\\n" + " ".join(words[mid:])

    # FFmpeg filtergraph:
    # 1. Crop 16:9 to 9:16 center (standard TEDx center speaker crop)
    # 2. Scale to target 1080x1920
    # 3. Optional drawtext banner at top
    filter_complex = f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={target_width}:{target_height}"
    
    if clean_hook:
        # Hook banner styling: white text with dark semi-transparent pill box
        drawtext = (
            f"drawtext=text='{clean_hook}':"
            f"fontsize=46:fontcolor=white:"
            f"box=1:boxcolor=black@0.65:boxborderw=18:"
            f"line_spacing=12:"
            f"x=(w-text_w)/2:y=240"
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
            print(f"   ✅ Rendered: {os.path.basename(output_path)} ({duration:.1f}s, {file_size_mb:.2f} MB)")
            return True
        else:
            print(f"   ❌ FFmpeg render error for {output_path}: {res.stderr.decode('utf-8', errors='ignore')[-300:]}")
            return False
    except Exception as e:
        print(f"   ❌ Error executing FFmpeg: {e}")
        return False
