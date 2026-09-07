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
    """Strips WebVTT inline tags like <00:00:19.680><c> and HTML tags/entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-z]+;|[><»«]", " ", text)
    return " ".join(text.split())


def parse_vtt_cues_robust(vtt_path: Path) -> List[Tuple[float, float, str]]:
    """
    Robust line-by-line WebVTT parser that handles irregular spacing,
    empty cues, and YouTube auto-caption formats without dropping lines.
    Returns list of (start_seconds, end_seconds, cleaned_text).
    """
    if not vtt_path or not vtt_path.exists():
        return []

    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    cues = []
    cur_time = None
    cur_text = []

    for line in content.splitlines():
        m = re.match(r"(\d+:\d+:[\d\.]+|\d+:[\d\.]+)\s*-->\s*(\d+:\d+:[\d\.]+|\d+:[\d\.]+)", line)
        if m:
            if cur_time and cur_text:
                c_start = parse_vtt_time(cur_time[0])
                c_end = parse_vtt_time(cur_time[1])
                combined = " ".join(cur_text).strip()
                if combined:
                    cues.append((c_start, c_end, combined))
            cur_time = (m.group(1), m.group(2))
            cur_text = []
        elif cur_time and line.strip():
            cleaned = clean_vtt_line(line)
            if cleaned:
                cur_text.append(cleaned)

    if cur_time and cur_text:
        c_start = parse_vtt_time(cur_time[0])
        c_end = parse_vtt_time(cur_time[1])
        combined = " ".join(cur_text).strip()
        if combined:
            cues.append((c_start, c_end, combined))

    return cues


def snap_clip_boundaries(
    vtt_path: Path,
    start_time: float,
    end_time: float,
    spoken_opening: str = "",
    lead_in: float = 0.35,
    lead_out: float = 0.35
) -> Tuple[float, float, float]:
    """
    Snaps LLM-estimated start/end timestamps to actual spoken word boundaries in the VTT.
    Returns:
        (snapped_start, snapped_end, vocal_start)
    where:
        snapped_start: Video cut start time (with acoustic lead_in pre-roll cushion).
        snapped_end: Video cut end time (with lead_out decay cushion).
        vocal_start: The exact timestamp where the speaker's first word begins in the VTT.
    """
    cues = parse_vtt_cues_robust(vtt_path)
    if not cues:
        vocal = round(start_time, 3)
        return max(0.0, round(start_time - lead_in, 3)), round(end_time + lead_out, 3), vocal

    # 1. Snap Start Time
    words = re.findall(r"\b\w+\b", spoken_opening.lower()) if spoken_opening else []
    first_word = words[0] if words else ""
    second_word = words[1] if len(words) > 1 else ""
    two_words = f"{first_word} {second_word}" if second_word else first_word

    start_cue_idx = None

    # Strategy A: Match opening words within a tight window (+- 2.5s) of start_time
    if first_word:
        candidates = []
        for i, (cs, ce, txt) in enumerate(cues):
            dist = abs(cs - start_time)
            if dist <= 2.5:
                txt_lower = txt.lower()
                if two_words and two_words in txt_lower:
                    candidates.append((0, dist, cs, i))
                elif first_word in txt_lower and second_word and second_word in txt_lower:
                    candidates.append((1, dist, cs, i))
                elif first_word in txt_lower and dist <= 1.2:
                    candidates.append((2, dist, cs, i))
        if candidates:
            # Sort by match quality first, then closest distance to start_time
            candidates.sort(key=lambda x: (x[0], x[1]))
            start_cue_idx = candidates[0][3]

    # Strategy B: If start_time lands inside a cue, snap to that cue's start
    if start_cue_idx is None:
        for i, (cs, ce, txt) in enumerate(cues):
            if cs <= start_time <= ce:
                start_cue_idx = i
                break

    # Strategy C: Closest cue within 2 seconds
    if start_cue_idx is None:
        closest = min(range(len(cues)), key=lambda i: abs(cues[i][0] - start_time))
        if abs(cues[closest][0] - start_time) < 2.0:
            start_cue_idx = closest

    if start_cue_idx is not None:
        raw_start = cues[start_cue_idx][0]
        # Check previous cue end time to avoid bleeding into prior sentence
        prev_end = cues[start_cue_idx - 1][1] if start_cue_idx > 0 else 0.0
        if prev_end < raw_start:
            snapped_start = max(raw_start - lead_in, prev_end + 0.02)
        else:
            snapped_start = raw_start - lead_in
        snapped_start = round(max(0.0, snapped_start), 3)
        vocal_start = round(raw_start, 3)
    else:
        vocal_start = round(start_time, 3)
        snapped_start = max(0.0, round(start_time - lead_in, 3))

    # 2. Snap End Time
    end_cue_idx = None
    for i, (cs, ce, txt) in enumerate(cues):
        if cs <= end_time <= ce:
            end_cue_idx = i
            break
        elif abs(ce - end_time) < 1.8:
            end_cue_idx = i

    if end_cue_idx is not None:
        raw_end = cues[end_cue_idx][1]
        next_start = cues[end_cue_idx + 1][0] if end_cue_idx + 1 < len(cues) else raw_end + 10.0
        if next_start > raw_end:
            snapped_end = min(raw_end + lead_out, next_start - 0.05)
        else:
            snapped_end = raw_end + lead_out
        snapped_end = round(snapped_end, 3)
    else:
        snapped_end = round(end_time + lead_out, 3)

    return snapped_start, snapped_end, vocal_start


def extract_clip_vtt_cues(
    vtt_path: Path,
    start_time: float,
    end_time: float,
    vocal_start: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Extracts raw spoken dialogue cues from WebVTT file within [start_time, end_time].
    Strictly excludes cues that finished before or at the vocal onset (prior sentence residue),
    preventing un-spoken words from the preceding context from flashing on screen.
    """
    cues_raw = parse_vtt_cues_robust(vtt_path)
    if not cues_raw:
        return []

    cues = []
    seen_texts = set()
    v_start = vocal_start if vocal_start is not None else start_time

    for c_start, c_end, combined_text in cues_raw:
        # Strictly exclude cues that finished before or right at vocal onset
        if c_end <= (v_start + 0.08):
            continue
        if c_start >= end_time:
            continue

        if c_end > start_time and c_start < end_time:
            rel_start = max(0.0, c_start - start_time)
            rel_end = min(end_time - start_time, c_end - start_time)

            # Ensure the first cue's subtitle does not appear before speech begins
            if c_start < v_start:
                rel_start = max(rel_start, round(v_start - start_time, 2))

            if combined_text and combined_text not in seen_texts:
                seen_texts.add(combined_text)
                cues.append({
                    "start": round(rel_start, 2),
                    "end": round(rel_end, 2),
                    "text": combined_text
                })

    return cues


def polish_subtitles_with_gemini(
    raw_cues: List[Dict[str, Any]],
    clip_duration: float,
    spoken_opening: str = "",
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

    from google.genai import types
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=location,
        http_options=types.HttpOptions(timeout=45000)
    )

    formatted_raw = "\n".join([f"[{c['start']}s - {c['end']}s] {c['text']}" for c in raw_cues])
    first_start = raw_cues[0]["start"] if raw_cues else 0.0
    opening_hint = f"\nThe speaker's opening sentence begins with: \"{spoken_opening}\". Do NOT include any dialogue or words before this opening sentence." if spoken_opening else ""

    prompt = f"""You are a professional video captions editor optimizing a {clip_duration:.1f}-second TEDx clip for Instagram Reels.{opening_hint}

Raw transcript with clip-relative timestamps:
{formatted_raw}

Task:
1. Fix transcription typos, misspellings, and proper nouns (e.g. Kerry places, Rossbeigh Beach, names).
2. Clean stuttering, false starts, and filler words ("um", "uh", "to to").
3. Preserve the exact words and cadence spoken by the speaker so the viewer reads what they hear.
4. Chunk the dialogue into punchy, high-retention 2 to 5 word subtitle lines (all UPPERCASE).
5. Ensure start and end timestamps match the speech flow between {first_start:.2f}s and {clip_duration:.1f}s. The first subtitle caption MUST NOT start before {first_start:.2f}s.
6. Return a strict JSON array of objects:
[
  {{"start": {first_start:.2f}, "end": {first_start + 1.8:.2f}, "text": "RECOMMENDED ACTIVITY:"}},
  {{"start": {first_start + 1.8:.2f}, "end": {first_start + 4.2:.2f}, "text": "WALKING IN A LOCAL PARK"}}
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
            # Enforce that the first subtitle does not display before vocal onset
            if data and data[0].get("start", 0.0) < first_start:
                data[0]["start"] = round(first_start, 2)
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
