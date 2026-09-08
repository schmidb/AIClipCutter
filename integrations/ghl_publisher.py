"""
GoHighLevel (GHL) Social Planner Integration.
Generates GHL-compliant CSV batch upload files and formatted metadata reports.
"""

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


def resolve_speaker_and_url(clip: Dict[str, Any]) -> tuple[str, str]:
    """Resolves speaker name and full YouTube URL from clip or config playlist files."""
    speaker = clip.get("speaker", "").strip()
    full_url = clip.get("full_video_url", "").strip()
    
    if speaker and full_url:
        return speaker, full_url

    # Check all playlist files in config
    playlist_files = list(Path("config").glob("playlist_*.json"))
    for playlist_path in playlist_files:
        if playlist_path.exists():
            try:
                with open(playlist_path, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                    video_list = pdata.get("videos", []) if isinstance(pdata, dict) else pdata
                    
                    # Match by video ID in media_url or source_video_title
                    search_text = f"{clip.get('media_url', '')} {clip.get('source_video_title', '')} {clip.get('cover_image', '')}"
                    for v in video_list:
                        vid_id = v.get("id", "")
                        if vid_id and vid_id in search_text:
                            if not speaker:
                                speaker = v.get("speaker", "")
                            if not full_url:
                                full_url = v.get("url", "")
                            return speaker, full_url
            except Exception:
                pass

    return speaker, full_url


def build_instagram_post_content(
    caption_text: str,
    speaker: str = "",
    full_video_url: str = "",
    hashtags: list = None,
    index: int = 0
) -> str:
    """
    Constructs a creative, dynamic Instagram Reel caption:
    1. Hook & core insight (personalizes generic references with real speaker name)
    2. Speaker attribution
    3. Full talk/keynote YouTube link
    4. Dynamically rotating CTA (save, share, follow, question, or bio link to prevent audience fatigue)
    5. Clean spacing with high-retention hashtags
    """
    body = caption_text.strip()
    if speaker and speaker.lower() != "tedx speaker":
        body = re.sub(r"\bThis TEDx speaker\b", f"Speaker {speaker}", body, flags=re.IGNORECASE)
        body = re.sub(r"\bThis speaker\b", f"Speaker {speaker}", body, flags=re.IGNORECASE)

    # Extract any hashtags embedded anywhere in the body text
    embedded_tags = re.findall(r"#\w+", body)
    body_no_tags = re.sub(r"#\w+\s*", "", body).strip()

    # Separate lines and clean up whitespace
    lines = []
    for line in body_no_tags.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        # If line is already a CTA, we will rebuild it cleanly
        if "Follow @" in line_clean or "Watch the full" in line_clean or "Speaker:" in line_clean or "Bookmark " in line_clean:
            continue
        lines.append(line_clean)

    main_copy = "\n\n".join(lines) if lines else body_no_tags

    # Call-to-action block
    cta_lines = []
    if speaker and speaker.lower() != "tedx speaker":
        cta_lines.append(f"🗣️ Speaker: {speaker}")
    if full_video_url:
        cta_lines.append(f"🔗 Watch the full talk: {full_video_url}")
    
    # Check if speaker is Miriam Schmidberger / Greator
    is_miriam = "miriam" in speaker.lower() if speaker else False

    if is_miriam:
        # Rotating CTAs for Miriam Schmidberger & Greator
        miriam_ctas = [
            "📌 Bookmark this reel for your morning routine or whenever you need clarity on your journey.",
            "✈️ Share this with someone who is ready to step out of the rat race and find their true 'Why'.",
            "🔗 Watch Miriam Schmidberger's full keynote from the Greator Festival via the link in bio!",
            "✨ Follow @miriam.schmidberger for more insights on purposeful living, authentic transformation, and mindset.",
            "💬 What part of your 'Why' are you stepping into today? Drop your thoughts below 👇"
        ]
        cta_lines.append(miriam_ctas[index % len(miriam_ctas)])
        default_tags = ["#MiriamSchmidberger", "#GreatorFestival", "#Greator", "#KnowYourWhy", "#PersonalGrowth", "#MindsetShift", "#Transformation"]
    else:
        # Rotating CTAs for TEDx Glenbeigh
        tedx_ctas = [
            "📌 Bookmark this reel whenever you need a mindful reset during a hectic work week.",
            "✈️ Send this to someone who needs to hear this reminder today 🌿",
            f"🔗 Watch {speaker}'s full 12-minute talk from TEDx Glenbeigh via the link in bio!",
            "✨ Follow @TEDxGlenbeigh for more inspiring TEDx talks and world-class ideas straight from Glenbeigh, in Co. Kerry! ☘️",
            "💬 Does this change how you think about your daily routine? Let us know below 👇"
        ]
        cta_lines.append(tedx_ctas[index % len(tedx_ctas)])
        default_tags = ["#TEDxGlenbeigh", "#TEDx", "#Glenbeigh", "#Kerry", "#Ireland", "#IdeasWorthSpreading"]

    if speaker and speaker.lower() not in ["tedx speaker", "speaker"]:
        speaker_tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", speaker)
        if speaker_tag not in default_tags:
            default_tags.insert(1, speaker_tag)

    combined_tags = []
    all_input_tags = (hashtags or []) + embedded_tags
    for tag in all_input_tags:
        t = tag.strip()
        if not t.startswith("#"):
            t = f"#{t}"
        if t not in combined_tags:
            combined_tags.append(t)
    for dt in default_tags:
        if dt not in combined_tags:
            combined_tags.append(dt)

    content_sections = [main_copy]
    if cta_lines:
        content_sections.append("\n".join(cta_lines))
    if combined_tags:
        content_sections.append(".\n.\n" + " ".join(combined_tags))

    return "\n\n".join(content_sections)


def build_linkedin_post_content(
    caption_text: str,
    speaker: str = "",
    full_video_url: str = "",
    hashtags: list = None,
    index: int = 0
) -> str:
    """
    Constructs a high-impact LinkedIn post:
    1. Hook & core thought-leadership insight
    2. Speaker attribution: 🎙️ Speaker: {speaker}
    3. Full episode/interview link: 🔗 Listen to the full story / interview: {full_video_url}
    4. Dynamically rotating LinkedIn CTA (comment debate, repost, full link, follow, or save)
    5. Clean, professional hashtags
    """
    body = caption_text.strip()
    embedded_tags = re.findall(r"#\w+", body)
    body_no_tags = re.sub(r"#\w+\s*", "", body).strip()

    lines = []
    for line in body_no_tags.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        if "Follow " in line_clean or "Listen to the full" in line_clean or "Watch the full" in line_clean or "Speaker:" in line_clean or "Repost " in line_clean:
            continue
        lines.append(line_clean)

    main_copy = "\n\n".join(lines) if lines else body_no_tags

    cta_lines = []
    if speaker:
        cta_lines.append(f"🎙️ Speaker: {speaker}")
    if full_video_url:
        cta_lines.append(f"🔗 Listen to the full story / interview: {full_video_url}")

    # Rotating CTAs for LinkedIn
    linkedin_ctas = [
        "💬 Where does your organization stand on this? Share your perspective in the comments below.",
        "♻️ Repost this to your network if you believe more enterprise leaders need this reality check.",
        "🎙️ Listen to Dr. Markus Schmidberger's full architectural breakdown at the link below.",
        "💼 Follow Dr. Markus Schmidberger on LinkedIn for actionable, hype-free enterprise AI and data leadership.",
        "📌 Save this post for your next executive AI strategy alignment meeting."
    ]
    cta_lines.append(linkedin_ctas[index % len(linkedin_ctas)])

    default_tags = ["#ArtificialIntelligence", "#AIStrategy", "#EnterpriseAI", "#Leadership", "#DigitalTransformation", "#MarkusSchmidberger"]
    combined_tags = []
    all_input_tags = (hashtags or []) + embedded_tags
    for tag in all_input_tags:
        t = tag.strip()
        if not t.startswith("#"):
            t = f"#{t}"
        if t not in combined_tags:
            combined_tags.append(t)
    for dt in default_tags:
        if dt not in combined_tags:
            combined_tags.append(dt)

    content_sections = [main_copy]
    if cta_lines:
        content_sections.append("\n".join(cta_lines))
    if combined_tags:
        content_sections.append(".\n.\n" + " ".join(combined_tags))

    return "\n\n".join(content_sections)


def mix_playlist_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evenly distributes and interleaves clips across speakers and source videos
    so that consecutive posts rotate speakers and content angles, avoiding fatigue.

    Example with Speakers A, B, C (5 clips each):
      Post 1: Speaker A, Clip 1 (Angle 1: Contrarian Take)
      Post 2: Speaker B, Clip 1 (Angle 1: Contrarian Take)
      Post 3: Speaker C, Clip 1 (Angle 1: Contrarian Take)
      Post 4: Speaker A, Clip 2 (Angle 2: Tactical Framework)
      ...
    """
    if not items:
        return []

    from collections import defaultdict
    grouped = defaultdict(list)
    speaker_order = []

    for item in items:
        spk = item.get("speaker") or item.get("source_video_title") or "Unknown"
        if spk not in speaker_order:
            speaker_order.append(spk)
        grouped[spk].append(item)

    mixed = []
    max_len = max(len(clips) for clips in grouped.values())
    for clip_idx in range(max_len):
        for spk in speaker_order:
            if clip_idx < len(grouped[spk]):
                mixed.append(grouped[spk][clip_idx])

    return mixed


def format_ghl_csv(
    clips_data: List[Dict[str, Any]],
    output_csv_path: str,
    start_date: datetime = None,
    end_date: datetime = None,
    post_interval_days: int = 1,
    post_time_hour: int = 18,  # 6:00 PM peak engagement
    post_time_minute: int = 0,
    platform: str = "Instagram"
) -> str:
    """
    Exports clip metadata to a GoHighLevel Social Planner compatible CSV file.
    Supports both Instagram Reels and LinkedIn thought leadership formats.
    Distributes posts evenly between start_date and end_date if end_date is provided.
    """
    if start_date is None:
        start_date = datetime.now() + timedelta(days=1)
    
    current_schedule_time = start_date.replace(
        hour=post_time_hour, minute=post_time_minute, second=0, microsecond=0
    )

    total_clips = len(clips_data)
    schedule_dates = []

    if end_date and total_clips > 1:
        # Evenly distribute posts across the calendar window
        total_days = (end_date.date() - start_date.date()).days
        for i in range(total_clips):
            offset_days = round(i * total_days / (total_clips - 1))
            dt = datetime.combine(
                start_date.date() + timedelta(days=offset_days),
                datetime.min.time()
            ).replace(hour=post_time_hour, minute=post_time_minute, second=0, microsecond=0)
            schedule_dates.append(dt)
    elif total_clips > 0:
        current_schedule_time = start_date.replace(
            hour=post_time_hour, minute=post_time_minute, second=0, microsecond=0
        )
        for _ in range(total_clips):
            schedule_dates.append(current_schedule_time)
            current_schedule_time += timedelta(days=post_interval_days)

    ghl_rows = []
    metadata_rows = []
    for i, clip in enumerate(clips_data):
        schedule_str = current_schedule_time.strftime("%Y-%m-%d %H:%M:%S")
        schedule_time = schedule_dates[i]
        schedule_str = schedule_time.strftime("%Y-%m-%d %H:%M:%S")
        
        caption_text = (
            clip.get("linkedin_post")
            or clip.get("caption")
            or clip.get("linkedin_caption")
            or clip.get("instagram_caption")
            or ""
        ).strip()
        hashtags = clip.get("hashtags", [])
        
        speaker, full_url = resolve_speaker_and_url(clip)
        
        if platform.lower() == "linkedin":
            full_content = build_linkedin_post_content(
                caption_text=caption_text,
                speaker=speaker or "Dr. Markus Schmidberger",
                full_video_url=full_url,
                hashtags=hashtags,
                index=i
            )
        else:
            full_content = build_instagram_post_content(
                caption_text=caption_text,
                speaker=speaker,
                full_video_url=full_url,
                hashtags=hashtags,
                index=i
            )
        
        media_url = clip.get("media_url", "")
        cover_image = clip.get("cover_image", "") or clip.get("cover_path", "")
        hook_banner = clip.get("hook_banner", "")
        
        # Video URL: GHL requires a valid public URL (e.g. http/https).
        # If media_url is a local file path, leave videoUrls empty so GHL imports the post
        # cleanly as a draft/scheduled post, allowing the user to attach the local clip in GHL.
        video_url_val = media_url if media_url.startswith(("http://", "https://")) else ""

        ghl_rows.append({
            "postAtSpecificTime (YYYY-MM-DD HH:mm:ss)": schedule_str,
            "content": full_content,
            "link (OGmetaUrl)": "",
            "imageUrls": "",
            "gifUrl": "",
            "videoUrls": video_url_val
        })

        metadata_rows.append({
            "Post Date": schedule_str,
            "Platform": platform,
            "Virality Score": clip.get("virality_score", ""),
            "Content Angle": clip.get("content_angle", ""),
            "Hook Banner": hook_banner,
            "Content": full_content,
            "Media URL": media_url,
            "Cover Image": cover_image,
            "Duration (sec)": clip.get("duration", 0),
            "Source Video": clip.get("source_video_title", "")
        })
        
        # Advance schedule date for the next post
        current_schedule_time += timedelta(days=post_interval_days)

    # Write GHL Social Planner compliant CSV
    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    ghl_fieldnames = [
        "postAtSpecificTime (YYYY-MM-DD HH:mm:ss)",
        "content",
        "link (OGmetaUrl)",
        "imageUrls",
        "gifUrl",
        "videoUrls"
    ]
    
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ghl_fieldnames)
        writer.writeheader()
        writer.writerows(ghl_rows)
        
    print(f"[GHL Publisher] Exported {len(ghl_rows)} posts to {output_path} (GHL Social Planner compliant)")

    # Also write local companion report with virality scores, angles, hook banners, cover paths, and durations
    meta_report_path = output_path.parent / f"{output_path.stem}_metadata_report.csv"
    meta_fieldnames = [
        "Post Date",
        "Platform",
        "Virality Score",
        "Content Angle",
        "Hook Banner",
        "Content",
        "Media URL",
        "Cover Image",
        "Duration (sec)",
        "Source Video"
    ]
    try:
        with open(meta_report_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=meta_fieldnames)
            writer.writeheader()
            writer.writerows(metadata_rows)
    except Exception:
        pass

    return str(output_path)


if __name__ == "__main__":
    # Test sample export
    sample_clips = [
        {
            "clip_index": 1,
            "duration": 14.5,
            "hook_banner": "THE LIE ABOUT SUCCESS NO ONE ADMITS",
            "caption": "What if everything you were told about success was backwards? 🤔\n\nAt TEDx Glenbeigh, this moment stopped the room.\n\n🎟️ TEDx Glenbeigh returns in 2027. Tap link in bio to join the waitlist!",
            "hashtags": ["#TEDx", "#TEDxGlenbeigh", "#IdeasWorthSpreading", "#Glenbeigh2027"],
            "media_url": "https://storage.googleapis.com/aiclipcutter-bucket/tedx/clip_01.mp4",
            "source_video_title": "Why you should take a walk in the park"
        }
    ]
    test_file = format_ghl_csv(sample_clips, "output/sample_ghl_posts.csv")
    print(f"Sample test generated at: {test_file}")

