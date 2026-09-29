"""
Gemini Audio Transcription with Timestamps.
Uses Gemini 2.0 Flash to transcribe audio and generate VTT format.
"""

import argparse
import os
import sys
from pathlib import Path

def transcribe_with_gemini(audio_path: str, output_vtt: str, project_id: str, max_chunk_minutes: int = 10):
    """Transcribe audio file using Gemini and output VTT format."""
    from google import genai
    from google.genai import types
    
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location="global",
        http_options=types.HttpOptions(timeout=300000)
    )
    
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    print(f"[Gemini Transcribe] Uploading {audio_file.name} ({audio_file.stat().st_size / 1024 / 1024:.1f} MB)...")
    
    # Upload the audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()
    
    prompt = """Transcribe this audio completely with accurate timestamps in VTT (WebVTT) subtitle format.

Output ONLY the VTT content, starting with "WEBVTT" header.

Format each cue as:
[timestamp_start] --> [timestamp_end]
[spoken text]

Use HH:MM:SS.mmm format for timestamps.
Keep each cue to 1-2 sentences max (5-10 seconds per cue).
Capture all speech accurately, including speaker names if identifiable.

Example:
WEBVTT

00:00:01.500 --> 00:00:05.200
When I first started working with AI in enterprise,

00:00:05.500 --> 00:00:09.800
I realized that most companies were approaching it completely wrong.

Begin transcription now:"""

    print("[Gemini Transcribe] Sending to Gemini 2.0 Flash for transcription...")
    
    # Determine mime type
    suffix = audio_file.suffix.lower()
    mime_map = {
        ".opus": "audio/opus",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
    }
    mime_type = mime_map.get(suffix, "audio/opus")
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=audio_data, mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=65536
        )
    )
    
    vtt_content = response.text.strip()
    
    # Clean up if wrapped in markdown code blocks
    if vtt_content.startswith("```"):
        lines = vtt_content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        vtt_content = "\n".join(lines)
    
    # Ensure WEBVTT header
    if not vtt_content.startswith("WEBVTT"):
        vtt_content = "WEBVTT\n\n" + vtt_content
    
    # Write output
    output_path = Path(output_vtt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
    
    # Count cues
    cue_count = vtt_content.count("-->")
    print(f"[Gemini Transcribe] ✅ Generated {cue_count} subtitle cues -> {output_vtt}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio with Gemini")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--output", required=True, help="Output VTT file path")
    parser.add_argument("--project", default=os.getenv("GCP_PROJECT_ID", ""), help="GCP Project ID")
    args = parser.parse_args()
    
    if not args.project:
        import subprocess
        result = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True)
        args.project = result.stdout.strip() if result.returncode == 0 else ""
    
    if not args.project:
        print("Error: No GCP project specified. Use --project or set GCP_PROJECT_ID")
        sys.exit(1)
    
    transcribe_with_gemini(args.audio, args.output, args.project)


if __name__ == "__main__":
    main()
