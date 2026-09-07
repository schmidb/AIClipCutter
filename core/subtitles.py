"""
AIClipCutter Subtitles Engine.
- Extracts dialogue cues from WebVTT
- Uses Gemini 3.8 Flash to polish transcription typos, remove verbal stutters, and format into punchy 2-5 word lines
- Generates high-retention ASS subtitles styled for Instagram Reels safe zones
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from google import genai
from google.genai import types


def parse_vtt_time(time_str: str) -> float:
    """Parses HH:MM:SS.mmm or MM:SS.mmm into total seconds."""
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def format_ass_time(seconds: float) -> str:
    """Formats seconds into ASS timestamp H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centis = int(round((secs - int(secs)) * 100))
    secs_int = int(secs)
    if centis >= 100:
        secs_int += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs_int:02d}.{centis:02d}"


def clean_vtt_line(text: str) -> str:
    """Strips WebVTT inline tags like <00:00:19.680><c> and HTML tags."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    return " ".join(text.split())


def extract_clip_vtt_cues(vtt_path: Path, start_time: float, end_time: float) -> List[Dict[str, Any]]:
    """
    Extracts raw spoken dialogue cues from WebVTT file within [start_time, end_time].
    Returns list of dicts with relative start/end times and text.
    """
    if not vtt_path.exists():
        return []

    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content)
    cues = []
    seen_texts = set()

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        time_match = None
        text_lines = []
        for line in lines:
            m = re.match(r"(\d+:\d+:[\d\.]+|\d+:[\d\.]+)\s*-->\s*(\d+:\d+:[\d\.]+|\d+:[\d\.]+)", line)
            if m:
                time_match = m
            elif time_match:
                cleaned = clean_vtt_line(line)
                if cleaned and cleaned not in seen_texts:
                    text_lines.append(cleaned)
                    seen_texts.add(cleaned)

        if time_match and text_lines:
            c_start = parse_vtt_time(time_match.group(1))
            c_end = parse_vtt_time(time_match.group(2))

            if c_end > start_time and c_start < end_time:
                rel_start = max(0.0, c_start - start_time)
                rel_end = min(end_time - start_time, c_end - start_time)
                combined_text = " ".join(text_lines)
                if combined_text:
                    cues.append({
                        "start": round(rel_start, 2),
                        "end": round(rel_end, 2),
                        "text": combined_text
                    })

    return cues


def polish_subtitles_with_gemini(
    raw_cues: List[Dict[str, Any]],
    clip_duration: float,
    project_id: str = "aiclipcutter-batch-7821",
    location: str = "global"
) -> List[Dict[str, Any]]:
    """
    Uses Gemini 3.8 Flash to polish transcription misspellings, eliminate verbal stumbles,
    and format dialogue into high-retention 2-5 word subtitle lines.
    """
    if not raw_cues:
        return []

    credentials_path = Path("config/gcp_service_account_key.json")
    if credentials_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path.resolve())

    client = genai.Client(vertexai=True, project=project_id, location=location)

    formatted_raw = "\n".join([f"[{c['start']}s - {c['end']}s] {c['text']}" for c in raw_cues])

    prompt = f"""You are a professional video captions editor optimizing a {clip_duration:.1f}-second TEDx clip for Instagram Reels.

Raw transcript with clip-relative timestamps:
{formatted_raw}

Task:
1. Fix transcription typos, misspellings, and proper nouns (e.g. Kerry places, Rossbeigh Beach, names).
2. Clean stuttering, false starts, and filler words ("um", "uh", "to to").
3. Preserve the exact words and cadence spoken by the speaker so the viewer reads what they hear.
4. Chunk the dialogue into punchy, high-retention 2 to 5 word subtitle lines (all UPPERCASE).
5. Ensure start and end timestamps match the speech flow between 0.0s and {clip_duration:.1f}s.
6. Return a strict JSON array of objects:
[
  {{"start": 0.0, "end": 1.8, "text": "RECOMMENDED ACTIVITY:"}},
  {{"start": 1.8, "end": 4.2, "text": "WALKING IN A LOCAL PARK"}}
]
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        data = json.loads(response.text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        print(f"⚠️ Gemini subtitle polish warning: {e}, using raw cues.")

    return [{"start": c["start"], "end": c["end"], "text": c["text"].upper()} for c in raw_cues]


def generate_ass_file(cues: List[Dict[str, Any]], output_ass_path: Path) -> Path:
    """
    Creates an ASS subtitle file styled for Instagram Reels:
    - Bold sans-serif typography
    - High-contrast white text with subtle black outline
    - Positioned in the safe zone (y ~ 1460, above the IG bottom bar)
    """
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1.5,0,1,4,2,2,50,50,460,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []
    for c in cues:
        s_time = format_ass_time(float(c.get("start", 0.0)))
        e_time = format_ass_time(float(c.get("end", 0.0)))
        txt = c.get("text", "").replace("\n", "\\n").strip()
        if txt:
            dialogue_lines.append(f"Dialogue: 0,{s_time},{e_time},Default,,0,0,0,,{txt}")

    full_ass = header + "\n".join(dialogue_lines) + "\n"
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(full_ass)

    return output_ass_path
