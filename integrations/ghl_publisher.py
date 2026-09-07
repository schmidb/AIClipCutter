"""
GoHighLevel (GHL) Social Planner Integration.
Generates GHL-compliant CSV batch upload files and formatted metadata reports.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


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
    
    Expected GHL CSV Columns:
    - Post At (YYYY-MM-DD HH:MM:SS)
    - Content (Caption + CTA + Hashtags)
    - Media URL (Direct MP4 URL)
    - Platforms (Optional account tagging)
    """
    if start_date is None:
        # Default start date: tomorrow
        start_date = datetime.now() + timedelta(days=1)
    
    current_schedule_time = start_date.replace(
        hour=post_time_hour, minute=post_time_minute, second=0, microsecond=0
    )

    rows = []
    for i, clip in enumerate(clips_data):
        schedule_str = current_schedule_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Combine caption and hashtags
        caption_text = (
            clip.get("caption")
            or clip.get("instagram_caption")
            or clip.get("linkedin_caption")
            or ""
        ).strip()
        hashtags = clip.get("hashtags", [])
        if isinstance(hashtags, list) and hashtags:
            hashtag_str = " ".join(hashtags)
            full_content = f"{caption_text}\n\n.\n.\n{hashtag_str}"
        else:
            full_content = caption_text
        
        media_url = clip.get("media_url", "")
        hook_banner = clip.get("hook_banner", "")
        
        rows.append({
            "Post Date": schedule_str,
            "Platform": platform,
            "Hook Banner": hook_banner,
            "Content": full_content,
            "Media URL": media_url,
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

