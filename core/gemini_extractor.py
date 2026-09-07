"""
Gemini Vertex AI Moment Extractor.
Uses Google Gemini (via Vertex AI) to analyze video transcripts,
hunt for 10-20 second high-impact moments, generate punchy hooks,
and create Instagram/LinkedIn copy.
"""

import os
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any
from google import genai
from google.genai import types


def load_preset(preset_path: str) -> Dict[str, Any]:
    with open(preset_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_viral_moments(
    transcript_text: str,
    preset_config: Dict[str, Any],
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global",
    model_name: str = "gemini-3.8-flash",
    speaker_name: str = "",
    video_title: str = "",
    full_video_url: str = ""
) -> List[Dict[str, Any]]:
    """
    Sends the video transcript to Gemini on Vertex AI and parses structured clips.
    """
    # Configure Vertex AI client
    credentials_path = Path("config/gcp_service_account_key.json")
    if credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path.resolve())

    from google.genai import types
    location_to_use = preset_config.get("gemini_location", location)
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=location_to_use,
        http_options=types.HttpOptions(timeout=60000)
    )

    model_to_use = preset_config.get("gemini_model", model_name)
    num_clips = preset_config.get("clips_per_video", 6)
    min_virality = int(preset_config.get("min_virality_score", 85))
    max_clips = int(preset_config.get("max_clips_per_video", num_clips or 8))
    min_dur = preset_config.get("min_duration_seconds", 10)
    max_dur = preset_config.get("max_duration_seconds", 20)
    system_prompt = preset_config.get("gemini_prompt", "")
    
    formatted_prompt = (
        system_prompt.replace("{num_clips}", str(max_clips))
        .replace("{max_clips}", str(max_clips))
        .replace("{min_virality_score}", str(min_virality))
        .replace("{min_duration}", str(min_dur))
        .replace("{max_duration}", str(max_dur))
        .replace("{speaker_name}", speaker_name or "the speaker")
        .replace("{video_title}", video_title or "this TEDx talk")
        .replace("{full_video_url}", full_video_url or "")
    )

    full_request = f"{formatted_prompt}\n\n=== FULL VIDEO TRANSCRIPT WITH TIMESTAMPS ===\n{transcript_text}"

    speaker_log = f" for '{speaker_name}'" if speaker_name else ""
    print(f"[Gemini Extractor] Querying Vertex AI ({model_to_use}){speaker_log} for viral moments (threshold >= {min_virality}%, max {max_clips} clips, {min_dur}-{max_dur}s)...")
    
    temp_to_use = float(preset_config.get("temperature", 0.75))
    response = client.models.generate_content(
        model=model_to_use,
        contents=full_request,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temp_to_use
        )
    )

    try:
        clips = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"[Gemini Extractor] Warning: Raw response not strict JSON: {e}")
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        clips = json.loads(text.strip())

    # Filter and sort clips by virality score
    filtered_clips = [
        c for c in clips if float(c.get("virality_score", 0)) >= min_virality
    ]
    if not filtered_clips:
        print(f"[Gemini Extractor] Notice: No clips met threshold >={min_virality}. Keeping top moments.")
        clips.sort(key=lambda x: float(x.get("virality_score", 0)), reverse=True)
        filtered_clips = clips[:max_clips]
    else:
        # Sort descending by virality score so highest-quality moments come first
        filtered_clips.sort(key=lambda x: float(x.get("virality_score", 0)), reverse=True)
        filtered_clips = filtered_clips[:max_clips]

    # Re-index and attach metadata to each moment
    for idx, clip in enumerate(filtered_clips, 1):
        clip["clip_index"] = idx
        if speaker_name:
            clip["speaker"] = speaker_name
        if full_video_url:
            clip["full_video_url"] = full_video_url
        if video_title:
            clip["source_video_title"] = video_title

    scores_str = ", ".join(f"#{c['clip_index']}:{c.get('virality_score')}" for c in filtered_clips)
    print(f"[Gemini Extractor] Successfully identified {len(filtered_clips)} viral moments ({scores_str}).")
    return filtered_clips


if __name__ == "__main__":
    # Smoke test with sample transcript snippet
    sample_preset = load_preset("config/tedx.yaml")
    sample_transcript = """
    [00:00:10.500 --> 00:00:15.200] When I first walked into the hospital room, I was terrified.
    [00:00:15.500 --> 00:00:22.000] Most people think that courage is the absence of fear, but it's actually moving forward while your knees are shaking.
    [00:00:22.500 --> 00:00:27.000] That single realization transformed the next twenty years of my entire career.
    [00:00:27.500 --> 00:00:35.000] You don't wait for fear to leave; you take it by the hand and walk into the room anyway.
    """
    results = extract_viral_moments(sample_transcript, sample_preset)
    print(json.dumps(results, indent=2))
