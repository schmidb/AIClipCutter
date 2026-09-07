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
    """Resolves speaker name and full YouTube URL from clip or playlist_tedx.json."""
    speaker = clip.get("speaker", "").strip()
    full_url = clip.get("full_video_url", "").strip()
    
    if speaker and full_url:
        return speaker, full_url

    # Check playlist_tedx.json
    playlist_path = Path("config/playlist_tedx.json")
    if playlist_path.exists():
        try:
            with open(playlist_path, "r", encoding="utf-8") as f:
                pdata = json.load(f)
                video_list = pdata.get("videos", [])
                
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
    hashtags: list = None
) -> str:
    """
    Constructs an Instagram Reel caption:
    1. Hook & core insight (personalizes generic references with real speaker name)
    2. Speaker attribution
    3. Full talk YouTube link
    4. Follow invitation for @TEDxGlenbeigh (Glenbeigh, Co. Kerry)
    5. Clean spacing with high-retention hashtags
    """
    body = caption_text.strip()
    if speaker and speaker.lower() != "tedx speaker":
        body = re.sub(r"\bThis TEDx speaker\b", f"Speaker {speaker}", body, flags=re.IGNORECASE)
        body = re.sub(r"\bThis speaker\b", f"Speaker {speaker}", body, flags=re.IGNORECASE)

    # Extract any hashtags embedded anywhere in the body text
    embedded_tags = re.findall(r"#\w+", body)
    # Remove the hashtags from the body text
    body_no_tags = re.sub(r"#\w+\s*", "", body).strip()

    # Separate lines and clean up whitespace
    lines = []
    for line in body_no_tags.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        # If line is already a CTA, we will rebuild it cleanly
        if "Follow @" in line_clean or "Watch the full talk" in line_clean or "Speaker:" in line_clean:
            continue
        lines.append(line_clean)

    main_copy = "\n\n".join(lines) if lines else body_no_tags

    # Call-to-action block
    cta_lines = []
    if speaker and speaker.lower() != "tedx speaker":
        cta_lines.append(f"🗣️ Speaker: {speaker}")
    if full_video_url:
        cta_lines.append(f"🔗 Watch the full talk: {full_video_url}")
    
    # Community & event follow CTA
    cta_lines.append(
        "✨ Follow @TEDxGlenbeigh for more inspiring TEDx talks and world-class ideas straight from Glenbeigh, in Co. Kerry! ☘️"
    )

    # Curated Hashtags
    default_tags = ["#TEDxGlenbeigh", "#TEDx", "#Glenbeigh", "#Kerry", "#Ireland", "#IdeasWorthSpreading"]
    if speaker and speaker.lower() != "tedx speaker":
        speaker_tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", speaker)
        if speaker_tag not in default_tags:
            default_tags.insert(2, speaker_tag)

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


def format_ghl_csv(
    clips_data: List[Dict[str, Any]],
    output_csv_path: str,
    start_date: datetime = None,
    post_interval_days: int = 1,
    post_time_hour: int = 18,  # 6:00 PM peak engagement
    post_time_minute: int = 0,
    platform: str = "Instagram"
) -> str:
    """
    Exports clip metadata to a GoHighLevel Social Planner compatible CSV file.
    """
    if start_date is None:
        start_date = datetime.now() + timedelta(days=1)
    
    current_schedule_time = start_date.replace(
        hour=post_time_hour, minute=post_time_minute, second=0, microsecond=0
    )

    rows = []
    for i, clip in enumerate(clips_data):
        schedule_str = current_schedule_time.strftime("%Y-%m-%d %H:%M:%S")
        
        caption_text = (
            clip.get("caption")
            or clip.get("instagram_caption")
            or clip.get("linkedin_caption")
            or ""
        ).strip()
        hashtags = clip.get("hashtags", [])
        
        speaker, full_url = resolve_speaker_and_url(clip)
        
        full_content = build_instagram_post_content(
            caption_text=caption_text,
            speaker=speaker,
            full_video_url=full_url,
            hashtags=hashtags
        )
        
        media_url = clip.get("media_url", "")
        cover_image = clip.get("cover_image", "") or clip.get("cover_path", "")
        hook_banner = clip.get("hook_banner", "")
        
        rows.append({
            "Post Date": schedule_str,
            "Platform": platform,
            "Hook Banner": hook_banner,
            "Content": full_content,
            "Media URL": media_url,
            "Cover Image": cover_image,
            "Duration (sec)": clip.get("duration", 0),
            "Source Video": clip.get("source_video_title", "")
        })
        
        # Advance schedule date for the next post
        current_schedule_time += timedelta(days=post_interval_days)

    # Write CSV
    output_path = Path(output_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "Post Date",
        "Platform",
        "Hook Banner",
        "Content",
        "Media URL",
        "Cover Image",
        "Duration (sec)",
        "Source Video"
    ]
    
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"[GHL Publisher] Exported {len(rows)} posts to {output_path}")
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

