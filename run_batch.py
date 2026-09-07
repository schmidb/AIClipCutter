"""
AIClipCutter Batch Pipeline Runner.
Runs the entire playlist locally (or in the cloud) with:
- AI Smart Centering (Gemini 3.8 Flash multimodal vision)
- High-precision 9:16 vertical video clipping with hook text banners
- Local high-speed rendering (10-20s per video)
- GoHighLevel Social Planner batch CSV scheduling (individual + master aggregated schedule)
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from run_single import process_single_video
from integrations.ghl_publisher import format_ghl_csv


def run_clip_engine_cloud(
    video_url: str,
    preset: str = "tedx",
    clips_count: int = 6,
    min_duration: int = 10,
    max_duration: int = 20,
    font_style: str = "HORMOZI",
    face_detector: str = "mediapipe"
) -> bool:
    """Invokes the legacy opensource-clipping engine in engine/main.py for cloud VM batch."""
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
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    gcp_key = Path("config/gcp_service_account_key.json").resolve()
    if gcp_key.exists():
        env["GOOGLE_APPLICATION_CREDENTIALS"] = str(gcp_key)

    process = subprocess.run(cmd, env=env)
    return process.returncode == 0


def create_master_ghl_schedule(all_rendered_items: list, output_csv_path: Path, platform: str = "Instagram"):
    """Aggregates all clips from all playlist videos into a single master GoHighLevel CSV."""
    if not all_rendered_items:
        return

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    start_date = datetime.now() + timedelta(days=1)
    format_ghl_csv(
        clips_data=all_rendered_items,
        output_csv_path=str(output_csv_path),
        start_date=start_date,
        post_interval_days=1,
        post_time_hour=18,
        platform=platform
    )
    print(f"\n🌟 Master GoHighLevel Schedule Created ({platform}):")
    print(f"   Path:  {output_csv_path.resolve()}")
    print(f"   Posts: {len(all_rendered_items)} scheduled across {len(all_rendered_items)} consecutive days at 6:00 PM")


def main():
    parser = argparse.ArgumentParser(description="AIClipCutter Batch Pipeline")
    parser.add_argument("--mode", default="local", choices=["local", "cloud"], help="Execution mode: 'local' (fast on PC) or 'cloud' (GCP VM)")
    parser.add_argument("--url", help="Single video URL to process")
    parser.add_argument("--playlist", default="config/playlist_tedx.json", help="Playlist JSON file")
    parser.add_argument("--preset", default="config/tedx.yaml", help="Path to preset YAML configuration")
    parser.add_argument("--platform", default="", help="Target platform (Instagram, LinkedIn, or auto)")
    parser.add_argument("--clips", type=int, default=6, help="Clips per video (default: 6)")
    parser.add_argument("--min-duration", type=int, default=10, help="Min duration in seconds")
    parser.add_argument("--max-duration", type=int, default=20, help="Max duration in seconds")
    parser.add_argument("--max-videos", type=int, default=None, help="Limit number of playlist videos to process")
    parser.add_argument("--min-virality", type=int, default=None, help="Minimum virality score threshold (0-100)")
    args = parser.parse_args()

    if args.preset in ["tedx", "linkedin", "miriam"]:
        args.preset = f"config/{args.preset}.yaml"

    # Determine videos to run
    video_targets = []
    playlist_meta = {}
    if args.url:
        video_targets.append({"url": args.url, "title": "Single Target Video"})
    elif args.playlist and Path(args.playlist).exists():
        with open(args.playlist, "r", encoding="utf-8") as f:
            playlist_meta = json.load(f)
            video_targets = playlist_meta.get("videos", []) if isinstance(playlist_meta, dict) else playlist_meta
        if args.max_videos and args.max_videos > 0:
            video_targets = video_targets[:args.max_videos]
        title = playlist_meta.get('playlist_title', args.playlist) if isinstance(playlist_meta, dict) else args.playlist
        print(f"📋 Loaded {len(video_targets)} videos to process from playlist: {title}")
    else:
        print("❌ Error: Please specify --url or --playlist")
        sys.exit(1)

    target_platform = (
        args.platform
        or (playlist_meta.get("platform") if isinstance(playlist_meta, dict) else "")
        or ("LinkedIn" if "linkedin" in args.preset.lower() else "Instagram")
    )

    print("\n" + "=" * 70)
    print(f"🚀 AIClipCutter Batch Processing — Mode: {args.mode.upper()}")
    print(f"Platform:       {target_platform}")
    print(f"Preset:         {args.preset}")
    print(f"Total Videos:   {len(video_targets)}")
    print(f"Clips / Video:  {args.clips or 'Dynamic (by Virality Threshold)'}")
    if args.min_virality:
        print(f"Virality Cut:   >= {args.min_virality}%")
    print(f"Centering:      AI Smart Centering (Gemini 3.8 Flash Vision)")
    print("=" * 70)

    all_master_items = []

    for i, target in enumerate(video_targets, 1):
        v_url = target["url"]
        v_title = target.get("title", f"Video {i}")
        v_speaker = target.get("speaker", "")
        print(f"\n============================================================")
        print(f"▶️ [VIDEO {i}/{len(video_targets)}] {v_title} ({v_speaker})")
        print(f"============================================================")

        if args.mode == "local":
            clips = process_single_video(
                url=v_url,
                preset=args.preset,
                clips=args.clips,
                step="all",
                video_title=v_title,
                speaker=v_speaker,
                platform=target_platform,
                min_virality=args.min_virality
            )
            for c in clips:
                all_master_items.append({
                    "duration": c.get("duration", 15),
                    "hook_banner": c.get("hook_banner", ""),
                    "virality_score": c.get("virality_score", 0),
                    "content_angle": c.get("content_angle", ""),
                    "caption": c.get("linkedin_post") or c.get("caption") or c.get("linkedin_caption") or c.get("instagram_caption") or "",
                    "hashtags": c.get("hashtags", []),
                    "media_url": c.get("local_path", ""),
                    "cover_image": c.get("cover_path", ""),
                    "speaker": c.get("speaker") or v_speaker,
                    "full_video_url": c.get("full_video_url") or v_url,
                    "source_video_title": v_title
                })
        else:
            success = run_clip_engine_cloud(
                video_url=v_url,
                preset="tedx",
                clips_count=args.clips,
                min_duration=args.min_duration,
                max_duration=args.max_duration
            )
            if not success:
                print(f"⚠️ Warning: Cloud processing for {v_url} finished with errors.")

    if args.mode == "local" and all_master_items:
        master_csv = Path("output/ghl_master_playlist_schedule.csv")
        create_master_ghl_schedule(all_master_items, master_csv, platform=target_platform)

    print("\n" + "=" * 70)
    print("🎉 All videos in batch processed successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
