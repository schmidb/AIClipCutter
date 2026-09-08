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
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from run_single import process_single_video
from integrations.ghl_publisher import format_ghl_csv


def create_master_ghl_schedule(
    all_rendered_items: list,
    output_csv_path: Path,
    master_clips_dir: Optional[Path] = None,
    platform: str = "Instagram",
    start_date: datetime = None,
    end_date: datetime = None,
    mix: bool = True
):
    """Aggregates all clips from all playlist videos into a single master GoHighLevel CSV."""
    if not all_rendered_items:
        return

    from integrations.ghl_publisher import mix_playlist_items

    if mix:
        all_rendered_items = mix_playlist_items(all_rendered_items)

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    if start_date is None:
        start_date = datetime(2026, 9, 15, 18, 0, 0)
    if end_date is None:
        end_date = datetime(2026, 12, 24, 18, 0, 0)

    format_ghl_csv(
        clips_data=all_rendered_items,
        output_csv_path=str(output_csv_path),
        start_date=start_date,
        end_date=end_date,
        post_time_hour=18,
        platform=platform
    )

    # Automatically organize sequential master clips into master_clips_dir
    if master_clips_dir is None:
        master_clips_dir = output_csv_path.parent / "ghl_master_clips"
    master_clips_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(all_rendered_items, 1):
        src_path = Path(item.get("media_url", ""))
        src_cover = Path(item.get("cover_image", ""))
        spk = "".join(c for c in item.get("speaker", "Speaker") if c.isalnum())
        dest_clip = master_clips_dir / f"{idx:02d}_{spk}_{src_path.name}"
        dest_cover = master_clips_dir / f"{idx:02d}_{spk}_{src_cover.name}"
        if src_path.exists():
            shutil.copy2(src_path, dest_clip)
        if src_cover.exists():
            shutil.copy2(src_cover, dest_cover)

    print(f"\n🌟 Master GoHighLevel Schedule Created ({platform}):")
    print(f"   CSV:   {output_csv_path.resolve()}")
    print(f"   Clips: {master_clips_dir.resolve()}")
    print(f"   Posts: {len(all_rendered_items)} scheduled from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')} at 6:00 PM (mixed={mix})")


def main():
    parser = argparse.ArgumentParser(description="AIClipCutter Batch Pipeline")
    parser.add_argument("--url", help="Single video URL to process")
    parser.add_argument("--playlist", default="config/playlist_tedx.json", help="Playlist JSON file")
    parser.add_argument("--preset", default=None, help="Path to preset YAML configuration")
    parser.add_argument("--platform", default="", help="Target platform (Instagram, LinkedIn, or auto)")
    parser.add_argument("--clips", type=int, default=None, help="Target clips per video (default: None, dynamic by virality threshold)")
    parser.add_argument("--min-duration", type=int, default=10, help="Min duration in seconds")
    parser.add_argument("--max-duration", type=int, default=20, help="Max duration in seconds")
    parser.add_argument("--max-videos", type=int, default=None, help="Limit number of playlist videos to process")
    parser.add_argument("--min-virality", type=int, default=None, help="Minimum virality score threshold (0-100)")
    parser.add_argument("--force", action="store_true", help="Force re-rendering clips even if they already exist")
    parser.add_argument("--start-date", default=None, help="Start date for master schedule (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="End date for master schedule (YYYY-MM-DD)")
    parser.add_argument("--no-mix", action="store_true", help="Disable round-robin speaker mixing in master playlist")
    parser.add_argument("--output-dir", help="Base directory for video processing files (default: output/markus for Markus/LinkedIn, else output)")
    parser.add_argument("--master-csv", help="Custom path for master GoHighLevel schedule CSV")
    parser.add_argument("--master-clips-dir", help="Custom directory for master sequential clips")
    args = parser.parse_args()

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

    chosen_preset = args.preset or playlist_meta.get("preset", "config/tedx.yaml")
    if chosen_preset in ["tedx", "linkedin", "miriam"]:
        chosen_preset = f"config/{chosen_preset}.yaml"

    target_platform = (
        args.platform
        or (playlist_meta.get("platform") if isinstance(playlist_meta, dict) else "")
        or ("LinkedIn" if "linkedin" in chosen_preset.lower() else "Instagram")
    )

    is_markus_or_linkedin = (
        "markus" in str(args.playlist).lower()
        or "linkedin" in chosen_preset.lower()
        or target_platform.lower() == "linkedin"
    )

    base_output_dir = Path(args.output_dir) if args.output_dir else (
        Path("output/markus") if is_markus_or_linkedin else Path("output")
    )
    master_csv = Path(args.master_csv) if args.master_csv else (
        Path("output/ghl_markus_schedule.csv") if is_markus_or_linkedin else Path("output/ghl_master_playlist_schedule.csv")
    )
    master_clips_dir = Path(args.master_clips_dir) if args.master_clips_dir else (
        Path("output/ghl_markus_clips") if is_markus_or_linkedin else Path("output/ghl_master_clips")
    )

    print("\n" + "=" * 70)
    print("🚀 AIClipCutter Batch Processing")
    print(f"Platform:       {target_platform}")
    print(f"Preset:         {chosen_preset}")
    print(f"Total Videos:   {len(video_targets)}")
    print(f"Clips / Video:  {args.clips or 'Dynamic (by Virality Threshold)'}")
    if args.min_virality:
        print(f"Virality Cut:   >= {args.min_virality}%")
    print(f"Output Dir:     {base_output_dir.resolve()}")
    print(f"Master CSV:     {master_csv.resolve()}")
    print(f"Master Clips:   {master_clips_dir.resolve()}")
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

        clips = process_single_video(
            url=v_url,
            preset=chosen_preset,
            clips=args.clips,
            step="all",
            video_title=v_title,
            speaker=v_speaker,
            platform=target_platform,
            min_virality=args.min_virality,
            force_rerender=args.force,
            output_dir=base_output_dir
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

    if all_master_items:
        default_start = "2026-09-15"
        default_end = "2026-11-30" if is_markus_or_linkedin else "2026-12-24"
        start_str = args.start_date or default_start
        end_str = args.end_date or default_end
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(hour=18, minute=0, second=0)
        except Exception:
            start_dt = datetime(2026, 9, 15, 18, 0, 0)
        try:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=18, minute=0, second=0)
        except Exception:
            end_dt = datetime(2026, 11, 30 if is_markus_or_linkedin else 12, 24, 18, 0, 0)
        create_master_ghl_schedule(
            all_rendered_items=all_master_items,
            output_csv_path=master_csv,
            master_clips_dir=master_clips_dir,
            platform=target_platform,
            start_date=start_dt,
            end_date=end_dt,
            mix=not args.no_mix
        )

    print("\n" + "=" * 70)
    print("🎉 All videos in batch processed successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
