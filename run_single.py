"""
AIClipCutter — Single Video Step-by-Step Pipeline Runner.

Run end-to-end:
    python run_single.py --url "https://www.youtube.com/watch?v=8pUxo0CZw5w"

Or run step-by-step:
    python run_single.py --url "..." --step download
    python run_single.py --url "..." --step moments
    python run_single.py --url "..." --step render
    python run_single.py --url "..." --step ghl
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

from core.gemini_extractor import extract_viral_moments
from core.compositor import render_vertical_clip
from integrations.ghl_publisher import format_ghl_csv


def extract_video_id(url: str) -> str:
    """Extract YouTube 11-char video ID."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else "sample_video"


def step_download(url: str, work_dir: Path) -> tuple[Path, Path]:
    """Step 1: Download video & English subtitles."""
    print("\n" + "=" * 60)
    print("📥 STEP 1: Downloading Video & Transcript via yt-dlp")
    print("=" * 60)

    source_video = work_dir / "source.mp4"
    
    # Download 720p/1080p MP4
    if not source_video.exists():
        print(f"Downloading video from {url}...")
        cmd_vid = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4][height<=720]/best[height<=720]",
            "--merge-output-format", "mp4",
            "-o", str(source_video),
            url
        ]
        res = subprocess.run(cmd_vid)
        if res.returncode != 0:
            print("⚠️ Falling back to best available format...")
            subprocess.run([sys.executable, "-m", "yt_dlp", "-o", str(source_video), url])
    else:
        print(f"✅ Source video already exists: {source_video}")

    # Download Subtitles (VTT)
    vtt_files = list(work_dir.glob("*.vtt"))
    vtt_path = vtt_files[0] if vtt_files else work_dir / "transcript.vtt"

    if not vtt_files:
        print("Fetching subtitles/transcript...")
        cmd_sub = [
            sys.executable, "-m", "yt_dlp",
            "--write-auto-subs",
            "--write-subs",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "-o", str(work_dir / "%(id)s"),
            url
        ]
        subprocess.run(cmd_sub)
        vtt_files = list(work_dir.glob("*.vtt"))
        vtt_path = vtt_files[0] if vtt_files else None

    print(f"✅ Video Path:      {source_video}")
    print(f"✅ Transcript Path: {vtt_path}")
    return source_video, vtt_path


def step_moments(vtt_path: Path, work_dir: Path, preset_path: str, clips_count: int) -> list:
    """Step 2: AI Moment Detection with Google Gemini Vertex AI."""
    print("\n" + "=" * 60)
    print("🧠 STEP 2: AI Moment Hunter (Google Gemini 3.8 Flash / Vertex AI)")
    print("=" * 60)

    moments_file = work_dir / "moments.json"
    if moments_file.exists():
        print(f"Found existing cached moments: {moments_file}")
        with open(moments_file, "r", encoding="utf-8") as f:
            return json.load(f)

    if not vtt_path or not vtt_path.exists():
        raise FileNotFoundError(f"Transcript file not found in {work_dir}")

    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        vtt_content = f.read()

    print(f"Analyzing transcript ({len(vtt_content)} bytes) using Vertex AI...")
    from core.gemini_extractor import load_preset
    preset_cfg = load_preset(preset_path)
    if clips_count:
        preset_cfg["clips_per_video"] = clips_count

    moments = extract_viral_moments(
        transcript_text=vtt_content,
        preset_config=preset_cfg
    )

    with open(moments_file, "w", encoding="utf-8") as f:
        json.dump(moments, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Identified {len(moments)} viral clips (10-20s):")
    for m in moments:
        dur = m.get("end_time", 0) - m.get("start_time", 0)
        print(f"   [{dur:4.1f}s] {m.get('hook_banner')} ({m.get('start_time')}s - {m.get('end_time')}s)")

    print(f"💾 Saved moments metadata to: {moments_file}")
    return moments


def step_render(source_video: Path, moments: list, work_dir: Path) -> list:
    """Step 3: Cut and render 9:16 vertical MP4 video clips."""
    print("\n" + "=" * 60)
    print("✂️ STEP 3: Cutting & Rendering 9:16 Vertical Video Clips (FFmpeg)")
    print("=" * 60)

    rendered_clips = []
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    for i, m in enumerate(moments, 1):
        clip_name = f"clip_{i}.mp4"
        clip_path = clips_dir / clip_name
        start_t = float(m.get("start_time", 0))
        end_t = float(m.get("end_time", start_t + 15))
        hook = m.get("hook_banner", "")

        print(f"\n🎬 Rendering Clip #{i}/{len(moments)}: {clip_name}")
        print(f"   Time Range: {start_t:.2f}s -> {end_t:.2f}s ({end_t - start_t:.1f}s)")
        print(f"   Hook:       {hook}")

        success = render_vertical_clip(
            source_video=str(source_video),
            start_time=start_t,
            end_time=end_t,
            output_path=str(clip_path),
            hook_banner=hook
        )

        if success:
            clip_meta = dict(m)
            clip_meta["local_path"] = str(clip_path)
            clip_meta["duration"] = round(end_t - start_t, 2)
            rendered_clips.append(clip_meta)

    print(f"\n🎉 Successfully rendered {len(rendered_clips)} clips in {clips_dir}!")
    return rendered_clips


def step_ghl(rendered_clips: list, work_dir: Path, video_title: str) -> Path:
    """Step 4: Format and Export GoHighLevel Social Planner CSV."""
    print("\n" + "=" * 60)
    print("📅 STEP 4: Exporting GoHighLevel Social Planner Schedule")
    print("=" * 60)

    # Optional sync to Google Cloud Storage bucket
    gcs_bucket = "aiclipcutter-media-7821"
    has_gcs = False

    # Check if gcloud / gsutil is authenticated
    try:
        res = subprocess.run(["gcloud", "auth", "print-access-token"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            has_gcs = True
    except Exception:
        pass

    ghl_items = []
    for item in rendered_clips:
        local_file = item.get("local_path", "")
        file_name = os.path.basename(local_file) if local_file else "clip.mp4"
        
        # Determine media URL for GHL
        if has_gcs and local_file and os.path.exists(local_file):
            gcs_path = f"gs://{gcs_bucket}/clips/{file_name}"
            public_url = f"https://storage.googleapis.com/{gcs_bucket}/clips/{file_name}"
            print(f"☁️ Syncing {file_name} to Google Cloud Storage...")
            subprocess.run(["gsutil", "cp", local_file, gcs_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            media_url = public_url
        else:
            # Local file reference for manual GHL upload
            media_url = local_file

        ghl_items.append({
            "duration": item.get("duration", 15),
            "hook_banner": item.get("hook_banner", ""),
            "caption": item.get("caption") or item.get("instagram_caption") or item.get("linkedin_caption") or "",
            "hashtags": item.get("hashtags", []),
            "media_url": media_url,
            "source_video_title": video_title
        })

    csv_path = work_dir / "ghl_social_planner_schedule.csv"
    format_ghl_csv(ghl_items, str(csv_path))

    print(f"\n✅ GoHighLevel CSV Ready:")
    print(f"   Path: {csv_path.resolve()}")
    print(f"   Import into: GoHighLevel > Marketing > Social Planner > CSV Upload")
    return csv_path


def main():
    parser = argparse.ArgumentParser(description="AIClipCutter Single Video Pipeline")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--preset", default="config/tedx.yaml", help="Preset config YAML (tedx or linkedin)")
    parser.add_argument("--clips", type=int, default=6, help="Target number of clips (default: 6)")
    parser.add_argument(
        "--step",
        default="all",
        choices=["all", "download", "moments", "render", "ghl"],
        help="Execute specific step or 'all'"
    )
    args = parser.parse_args()

    # Create dedicated output directory for this video
    video_id = extract_video_id(args.url)
    work_dir = Path("output") / video_id
    work_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(f"🎬 AIClipCutter — Single Video Mode")
    print(f"Video URL:    {args.url}")
    print(f"Video ID:     {video_id}")
    print(f"Working Dir:  {work_dir.resolve()}")
    print(f"Preset:       {args.preset}")
    print(f"Step:         {args.step}")
    print("=" * 70)

    source_video = work_dir / "source.mp4"
    vtt_path = None
    moments = []
    rendered_clips = []

    # Check for existing VTT if already downloaded
    existing_vtt = list(work_dir.glob("*.vtt"))
    if existing_vtt:
        vtt_path = existing_vtt[0]

    # Check for existing moments.json
    moments_file = work_dir / "moments.json"
    if moments_file.exists():
        with open(moments_file, "r", encoding="utf-8") as f:
            moments = json.load(f)

    # Execute selected steps
    if args.step in ["all", "download"]:
        source_video, vtt_path = step_download(args.url, work_dir)

    if args.step in ["all", "moments"]:
        if not vtt_path or not vtt_path.exists():
            source_video, vtt_path = step_download(args.url, work_dir)
        moments = step_moments(vtt_path, work_dir, args.preset, args.clips)

    if args.step in ["all", "render"]:
        if not source_video.exists():
            source_video, _ = step_download(args.url, work_dir)
        if not moments:
            moments = step_moments(vtt_path, work_dir, args.preset, args.clips)
        rendered_clips = step_render(source_video, moments, work_dir)

    if args.step in ["all", "ghl"]:
        if not rendered_clips:
            # Look for existing clips in clips_dir
            clips_dir = work_dir / "clips"
            if clips_dir.exists() and moments:
                for i, m in enumerate(moments, 1):
                    clip_file = clips_dir / f"clip_{i}.mp4"
                    if clip_file.exists():
                        cm = dict(m)
                        cm["local_path"] = str(clip_file)
                        cm["duration"] = round(float(m.get("end_time", 0)) - float(m.get("start_time", 0)), 2)
                        rendered_clips.append(cm)
        step_ghl(rendered_clips, work_dir, f"TEDx Talk ({video_id})")

    print("\n" + "=" * 70)
    print("✅ Finished processing single video!")
    print(f"📂 Open your files at: {work_dir.resolve()}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
