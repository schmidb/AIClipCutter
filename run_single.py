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
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path

from core.gemini_extractor import extract_viral_moments
from core.compositor import render_vertical_clip
from core.subtitles import extract_clip_vtt_cues, polish_subtitles_with_gemini, generate_ass_file, snap_clip_boundaries
from integrations.ghl_publisher import format_ghl_csv


def extract_video_id(url: str) -> str:
    """Extract YouTube 11-char video ID."""
    if url and len(url) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url):
        return url
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else "sample_video"


def get_video_info(url_or_id: str) -> dict:
    """Resolves speaker, title, and YouTube URL from config playlists if available."""
    video_id = extract_video_id(url_or_id)
    playlist_files = list(Path("config").glob("playlist_*.json"))
    for playlist_path in playlist_files:
        if playlist_path.exists():
            try:
                with open(playlist_path, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                    video_list = pdata.get("videos", []) if isinstance(pdata, dict) else pdata
                    for v in video_list:
                        if v.get("id") == video_id or video_id in v.get("url", ""):
                            return {
                                "id": v.get("id"),
                                "title": v.get("title", f"Video ({video_id})"),
                                "speaker": v.get("speaker", "Speaker"),
                                "url": v.get("url", f"https://www.youtube.com/watch?v={video_id}")
                            }
            except Exception:
                pass
    return {
        "id": video_id,
        "title": f"Video ({video_id})",
        "speaker": "Speaker",
        "url": f"https://www.youtube.com/watch?v={video_id}"
    }


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


def step_moments(
    vtt_path: Path,
    work_dir: Path,
    preset_path: str = "config/tedx.yaml",
    clips_count: int = None,
    speaker_name: str = "",
    video_title: str = "",
    full_video_url: str = "",
    min_virality: int = None
) -> list:
    """Step 2: AI Moment Hunter via Gemini 3.8 Flash."""
    print("\n" + "=" * 60)
    print("🧠 STEP 2: AI Moment Hunter (Google Gemini 3.8 Flash / Vertex AI)")
    print("=" * 60)

    moments_file = work_dir / "moments.json"

    if moments_file.exists():
        try:
            with open(moments_file, "r", encoding="utf-8") as f:
                cached_moments = json.load(f)
            if cached_moments and isinstance(cached_moments, list) and len(cached_moments) > 0:
                print(f"✅ Loaded {len(cached_moments)} cached viral moments from: {moments_file}")
                return cached_moments
        except Exception:
            pass

    if not vtt_path or not vtt_path.exists():
        raise FileNotFoundError(f"Transcript file not found in {work_dir}")

    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        vtt_content = f.read()

    print(f"Analyzing transcript ({len(vtt_content)} bytes) using Vertex AI...")
    from core.gemini_extractor import load_preset
    preset_cfg = load_preset(preset_path)
    if clips_count:
        preset_cfg["clips_per_video"] = clips_count
        preset_cfg["max_clips_per_video"] = clips_count
    if min_virality is not None:
        preset_cfg["min_virality_score"] = min_virality

    moments = extract_viral_moments(
        transcript_text=vtt_content,
        preset_config=preset_cfg,
        speaker_name=speaker_name,
        video_title=video_title,
        full_video_url=full_video_url
    )

    with open(moments_file, "w", encoding="utf-8") as f:
        json.dump(moments, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Identified {len(moments)} viral clips (10-20s):")
    for m in moments:
        dur = m.get("end_time", 0) - m.get("start_time", 0)
        print(f"   [{dur:4.1f}s] {m.get('hook_banner')} ({m.get('start_time')}s - {m.get('end_time')}s)")

    print(f"💾 Saved moments metadata to: {moments_file}")
    return moments


def step_render(
    source_video: Path,
    moments: list,
    work_dir: Path,
    force_rerender: bool = False,
    preset: str = "",
    speaker_name: str = "",
    platform: str = ""
) -> list:
    """Step 3: Cut and render 9:16 vertical MP4 video clips with VTT speech-boundary snapping."""
    print("\n" + "=" * 60)
    print("✂️ STEP 3: Cutting & Rendering 9:16 Vertical Video Clips (Speech Snapping + AI Smart Centering + Subtitles + FFmpeg)")
    print("=" * 60)

    rendered_clips = []
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    # Detect VTT subtitle file for spoken dialogue sync
    vtt_files = list(work_dir.glob("*.vtt"))
    vtt_path = vtt_files[0] if vtt_files else None

    # Subtitle directory (persisted so re-renders reuse polished subtitles)
    subs_dir = work_dir / "subtitles"
    subs_dir.mkdir(exist_ok=True)

    # Determine badge text and color based on platform / preset / speaker
    is_linkedin = "linkedin" in preset.lower() or platform.lower() == "linkedin" or "markus" in speaker_name.lower()
    if is_linkedin:
        badge_text = "Dr. Markus Schmidberger"
        badge_color = (10, 102, 194, 240)  # Official LinkedIn Blue #0A66C2
    elif "miriam" in speaker_name.lower() or "miriam" in preset.lower():
        badge_text = "Miriam Schmidberger"
        badge_color = (220, 80, 50, 240)
    else:
        badge_text = "TEDxGlenbeigh"
        badge_color = (235, 0, 40, 240)  # Official TED Red #EB0028

    for i, m in enumerate(moments, 1):
        clip_idx = m.get("clip_index", i)
        clip_name = f"clip_{clip_idx}.mp4"
        clip_path = clips_dir / clip_name

        orig_start = float(m.get("start_time", 0))
        orig_end = float(m.get("end_time", 0))
        spoken_opening = m.get("spoken_opening", "")

        # Intelligent VTT speech boundary snapping with acoustic pre-roll cushion
        start_t = orig_start
        end_t = orig_end
        vocal_t = orig_start
        if vtt_path and vtt_path.exists():
            snapped_s, snapped_e, vocal_t = snap_clip_boundaries(
                vtt_path=vtt_path,
                start_time=orig_start,
                end_time=orig_end,
                spoken_opening=spoken_opening,
                lead_in=0.35,
                lead_out=0.35
            )
            if snapped_s != orig_start or snapped_e != orig_end:
                diff_ms = (orig_start - snapped_s) * 1000
                print(f"\n⏱️ Clip #{clip_idx}: Snapped to Speech Boundary: {orig_start:.2f}s -> {snapped_s:.2f}s ({diff_ms:+.0f}ms pre-roll), end={orig_end:.2f}s -> {snapped_e:.2f}s (vocal={vocal_t:.2f}s)")
                start_t = snapped_s
                end_t = snapped_e
                m["start_time"] = start_t
                m["end_time"] = end_t

        duration = round(end_t - start_t, 2)
        m["duration"] = duration
        hook = m.get("hook_banner", "")

        if not force_rerender and clip_path.exists() and clip_path.stat().st_size > 500000:
            print(f"\n🎬 Clip #{clip_idx}/{len(moments)} already rendered: {clip_name} ({clip_path.stat().st_size / 1024 / 1024:.2f} MB)")
            clip_meta = dict(m)
            clip_meta["local_path"] = str(clip_path)
            cover_file = clips_dir / f"cover_{clip_idx}.jpg"
            if cover_file.exists():
                clip_meta["cover_path"] = str(cover_file)
            clip_meta["duration"] = round(duration, 2)
            rendered_clips.append(clip_meta)
            continue

        print(f"\n🎬 Rendering Clip #{clip_idx}/{len(moments)}: {clip_name}")
        print(f"   Time Range: {start_t:.2f}s -> {end_t:.2f}s ({duration:.1f}s)")
        print(f"   Opening:    \"{spoken_opening[:50]}\"")
        print(f"   Hook:       {hook}")

        # AI Subtitle Polishing (Fix typos, Irish place names, verbal stutters)
        ass_path = None
        target_ass = subs_dir / f"clip_{clip_idx}.ass"
        if target_ass.exists() and target_ass.stat().st_size > 50:
            print(f"   📝 Reusing cached subtitle file: {target_ass.name}")
            ass_path = str(target_ass)
        elif vtt_path and vtt_path.exists():
            raw_cues = extract_clip_vtt_cues(vtt_path, start_t, end_t, vocal_start=vocal_t)
            if raw_cues:
                print(f"   📝 Polishing {len(raw_cues)} subtitle cues with Gemini 3.8 Flash...")
                polished_cues = polish_subtitles_with_gemini(
                    raw_cues, duration, spoken_opening=spoken_opening
                )
                generate_ass_file(polished_cues, target_ass)
                ass_path = str(target_ass)

        success = render_vertical_clip(
            source_video=str(source_video),
            start_time=start_t,
            end_time=end_t,
            output_path=str(clip_path),
            hook_banner=hook,
            enable_ai_centering=True,
            ass_path=ass_path,
            generate_cover=True,
            badge_text=badge_text,
            badge_color=badge_color
        )

        if success:
            clip_meta = dict(m)
            clip_meta["local_path"] = str(clip_path)
            cover_file = clips_dir / f"cover_{clip_idx}.jpg"
            if cover_file.exists():
                clip_meta["cover_path"] = str(cover_file)
            clip_meta["duration"] = round(duration, 2)
            rendered_clips.append(clip_meta)

    # Persist updated moment boundaries to moments.json
    try:
        moments_file = work_dir / "moments.json"
        with open(moments_file, "w", encoding="utf-8") as f:
            json.dump(moments, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Warning saving updated moments.json: {e}")

    print(f"\n🎉 Successfully rendered {len(rendered_clips)} clips in {clips_dir}!")
    return rendered_clips


def step_ghl(
    rendered_clips: list,
    work_dir: Path,
    video_title: str,
    speaker_name: str = "",
    full_video_url: str = "",
    platform: str = "Instagram"
) -> Path:
    """Step 4: Format and Export GoHighLevel Social Planner CSV."""
    print("\n" + "=" * 60)
    print(f"📅 STEP 4: Exporting GoHighLevel Social Planner Schedule ({platform})")
    print("=" * 60)

    # Optional sync to Google Cloud Storage bucket
    gcs_bucket = os.getenv("GCS_BUCKET_NAME", "")
    has_gcs = False

    if gcs_bucket:
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
            media_url = local_file

        ghl_items.append({
            "duration": item.get("duration", 15),
            "hook_banner": item.get("hook_banner", ""),
            "virality_score": item.get("virality_score", 0),
            "content_angle": item.get("content_angle", ""),
            "caption": item.get("caption") or item.get("linkedin_post") or item.get("linkedin_caption") or item.get("instagram_caption") or "",
            "hashtags": item.get("hashtags", []),
            "media_url": media_url,
            "cover_image": item.get("cover_path", ""),
            "speaker": item.get("speaker") or speaker_name,
            "full_video_url": item.get("full_video_url") or full_video_url,
            "source_video_title": video_title
        })

    csv_path = work_dir / "ghl_social_planner_schedule.csv"
    format_ghl_csv(ghl_items, str(csv_path), platform=platform)

    print(f"\n✅ GoHighLevel CSV Ready ({platform}):")
    print(f"   Path: {csv_path.resolve()}")
    print(f"   Import into: GoHighLevel > Marketing > Social Planner > CSV Upload")
    return csv_path


def process_single_video(
    url: str,
    preset: str = "config/tedx.yaml",
    clips: int = None,
    step: str = "all",
    video_title: str = "",
    speaker: str = "",
    platform: str = None,
    min_virality: int = None,
    force_rerender: bool = False,
    output_dir: Optional[Path] = None
) -> list:
    """Processes a single video: downloads, hunts moments, renders clips, and creates GHL schedule."""
    video_id = extract_video_id(url)
    vinfo = get_video_info(url)
    speaker_name = speaker or vinfo.get("speaker", "")
    full_video_url = vinfo.get("url", url)
    display_title = video_title or vinfo.get("title", f"Video ({video_id})")

    if preset in ["tedx", "linkedin", "miriam"]:
        preset = f"config/{preset}.yaml"

    if preset == "config/tedx.yaml":
        if "miriam" in speaker_name.lower() or "qRqt7_W37J4" in url:
            preset = "config/miriam.yaml"
        elif "markus" in speaker_name.lower():
            preset = "config/linkedin.yaml"

    target_platform = platform or ("LinkedIn" if "linkedin" in preset.lower() else "Instagram")
    if output_dir is not None:
        work_dir = Path(output_dir) / video_id
    else:
        work_dir = Path("output") / video_id
    work_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(f"🎬 AIClipCutter — Single Video Mode")
    print(f"Video URL:    {url}")
    print(f"Video ID:     {video_id}")
    print(f"Speaker:      {speaker_name}")
    print(f"Title:        {display_title}")
    print(f"Platform:     {target_platform}")
    print(f"Working Dir:  {work_dir.resolve()}")
    print(f"Preset:       {preset}")
    print(f"Step:         {step}")
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
    if step in ["all", "download"]:
        source_video, vtt_path = step_download(url, work_dir)

    if step in ["all", "moments"]:
        if not vtt_path or not vtt_path.exists():
            _, vtt_path = step_download(url, work_dir)
        moments = step_moments(
            vtt_path=vtt_path,
            work_dir=work_dir,
            preset_path=preset,
            clips_count=clips,
            speaker_name=speaker_name,
            video_title=display_title,
            full_video_url=full_video_url,
            min_virality=min_virality
        )

    if step in ["all", "render"]:
        if not source_video.exists():
            source_video, _ = step_download(url, work_dir)
        if not moments:
            moments = step_moments(
                vtt_path=vtt_path,
                work_dir=work_dir,
                preset_path=preset,
                clips_count=clips,
                speaker_name=speaker_name,
                video_title=display_title,
                full_video_url=full_video_url,
                min_virality=min_virality
            )
        rendered_clips = step_render(
            source_video=source_video,
            moments=moments,
            work_dir=work_dir,
            force_rerender=force_rerender,
            preset=preset,
            speaker_name=speaker_name,
            platform=target_platform
        )

    if step in ["all", "ghl"]:
        if not rendered_clips:
            clips_dir = work_dir / "clips"
            if clips_dir.exists() and moments:
                for i, m in enumerate(moments, 1):
                    clip_file = clips_dir / f"clip_{i}.mp4"
                    if clip_file.exists():
                        cm = dict(m)
                        cm["local_path"] = str(clip_file)
                        cover_file = clips_dir / f"cover_{i}.jpg"
                        if cover_file.exists():
                            cm["cover_path"] = str(cover_file)
                        cm["duration"] = round(float(m.get("end_time", 0)) - float(m.get("start_time", 0)), 2)
                        rendered_clips.append(cm)
        step_ghl(
            rendered_clips=rendered_clips,
            work_dir=work_dir,
            video_title=display_title,
            speaker_name=speaker_name,
            full_video_url=full_video_url,
            platform=target_platform
        )

    print("\n" + "=" * 70)
    print("✅ Finished processing single video!")
    print(f"📂 Open your files at: {work_dir.resolve()}")
    print("=" * 70 + "\n")
    return rendered_clips


def main():
    parser = argparse.ArgumentParser(description="AIClipCutter Single Video Pipeline")
    parser.add_argument("--url", default="https://www.youtube.com/watch?v=8pUxo0CZw5w", help="YouTube video URL")
    parser.add_argument("--speaker", default="", help="Speaker name (optional)")
    parser.add_argument("--title", default="", help="Video title (optional)")
    parser.add_argument("--preset", default="config/tedx.yaml", help="Path to preset YAML configuration")
    parser.add_argument("--platform", default="", help="Target platform (Instagram, LinkedIn, or auto)")
    parser.add_argument("--clips", type=int, default=None, help="Target number of clips to produce")
    parser.add_argument("--min-virality", type=int, default=None, help="Minimum virality score threshold (0-100)")
    parser.add_argument("--force", action="store_true", help="Force re-rendering even if clip files already exist")
    parser.add_argument(
        "--step",
        default="all",
        choices=["all", "download", "moments", "render", "ghl"],
        help="Execute specific step or 'all'"
    )
    args = parser.parse_args()
    process_single_video(
        url=args.url,
        preset=args.preset,
        clips=args.clips,
        step=args.step,
        video_title=args.title,
        speaker=args.speaker,
        platform=args.platform or None,
        min_virality=args.min_virality,
        force_rerender=args.force
    )


if __name__ == "__main__":
    main()
