"""
AIClipCutter Batch Pipeline Runner.
Orchestrates NaufalRizqullah/opensource-clipping engine with:
- TEDx Glenbeigh 2027 and LinkedIn Presets
- Strict 10-20s duration constraints
- Google Cloud Vertex AI & Google Cloud Credits
- GoHighLevel Social Planner batch CSV scheduling
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from integrations.ghl_publisher import format_ghl_csv


def run_clip_engine(
    video_url: str,
    preset: str = "tedx",
    clips_count: int = 6,
    min_duration: int = 10,
    max_duration: int = 20,
    font_style: str = "HORMOZI",
    face_detector: str = "mediapipe",
    output_dir: str = "output"
) -> list:
    """
    Invokes the opensource-clipping engine located in engine/main.py.
    """
    engine_main = Path("engine/main.py").resolve()
    
    cmd = [
        sys.executable,
        str(engine_main),
        "--url", video_url,
        "--clips", str(clips_count),
        "--ratio", "9:16",
        "--font-style", font_style,
        "--face-detector", face_detector,
        "--preset", preset,
        "--min-duration", str(min_duration),
        "--max-duration", str(max_duration),
        "--hook-v2",
        "--export-ghl"
    ]

    print("\n" + "=" * 60)
    print(f"🎬 Running OpenSource Clipping Engine")
    print(f"URL:          {video_url}")
    print(f"Preset:       {preset}")
    print(f"Target Clips: {clips_count} ({min_duration}-{max_duration}s)")
    print(f"Subtitle:     {font_style} (Kinetic Karaoke)")
    print("=" * 60)
    print("Command:\n" + " ".join(cmd))
    print("=" * 60 + "\n")

    # Set UTF-8 and GCP credentials in environment
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    gcp_key = Path("config/gcp_service_account_key.json").resolve()
    if gcp_key.exists():
        env["GOOGLE_APPLICATION_CREDENTIALS"] = str(gcp_key)

    process = subprocess.run(cmd, env=env)
    return process.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="AIClipCutter Batch Pipeline")
    parser.add_argument("--url", help="Single video URL to process")
    parser.add_argument("--playlist", default="config/playlist_tedx.json", help="Playlist JSON file")
    parser.add_argument("--preset", default="tedx", choices=["tedx", "linkedin", "default"], help="Content preset")
    parser.add_argument("--clips", type=int, default=6, help="Clips per video (default: 6)")
    parser.add_argument("--min-duration", type=int, default=10, help="Min duration in seconds")
    parser.add_argument("--max-duration", type=int, default=20, help="Max duration in seconds")
    parser.add_argument("--font-style", default="HORMOZI", help="Subtitle font style (HORMOZI, STORYTELLER, etc.)")
    args = parser.parse_args()

    # Determine videos to run
    video_targets = []
    if args.url:
        video_targets.append({"url": args.url, "title": "Single Target Video"})
    elif args.playlist and Path(args.playlist).exists():
        with open(args.playlist, "r", encoding="utf-8") as f:
            data = json.load(f)
            video_targets = data.get("videos", [])
        print(f"Loaded {len(video_targets)} videos from playlist: {data.get('playlist_title')}")
    else:
        print("❌ Error: Please specify --url or --playlist")
        sys.exit(1)

    for i, target in enumerate(video_targets, 1):
        print(f"\n▶️ Starting Video {i}/{len(video_targets)}: {target.get('title')}")
        success = run_clip_engine(
            video_url=target["url"],
            preset=args.preset,
            clips_count=args.clips,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            font_style=args.font_style
        )
        if not success:
            print(f"⚠️ Warning: Processing video {target['url']} completed with errors.")

    print("\n🎉 Batch processing completed!")


if __name__ == "__main__":
    main()
