# AIClipCutter 🎬⚡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AI Engine](https://img.shields.io/badge/AI-Gemini%203.8%20Flash-orange.svg)](https://deepmind.google/technologies/gemini/)
[![Video Engine](https://img.shields.io/badge/Engine-FFmpeg-green.svg)](https://ffmpeg.org/)

> **Autonomous Long-to-Short Video Repurposing Pipeline powered by Google Gemini 3.8 Flash & FFmpeg**

AIClipCutter transforms 10–60 minute long-form YouTube videos (talks, keynotes, podcast interviews) into viral, high-retention 10–30 second vertical clips (9:16) formatted and scheduled directly for **Instagram Reels**, **TikTok**, and **LinkedIn** via **GoHighLevel (GHL)**.

---

## 🏗️ Architecture & How It Works

AIClipCutter runs an ultra-fast, native Python pipeline that requires zero heavy local deep-learning libraries or CUDA dependencies:

```
                       [ Long-Form YouTube Video ]
                                    │
                                    ▼
                     yt-dlp (Video & VTT Auto-Captions)
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   🧠 Step 1: AI Moment Hunter (Google Gemini 3.8 Flash) │
       │   • Evaluates virality (0-100 score threshold)         │
       │   • Enforces duration constraints (e.g., 10-25s)       │
       │   • Categorizes distinct creative content angles       │
       │   • Writes platform-tailored captions, hooks & CTAs    │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   ⏱️ Step 2: Speech-Onset Snapping (core/subtitles.py)   │
       │   • Snaps LLM timestamps to exact VTT syllable onset   │
       │   • Adds +0.35s acoustic pre-roll room-tone cushion    │
       │   • Completely eliminates clipped opening words        │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   🎯 Step 3: Smart Auto-Framing (core/compositor.py)   │
       │   • Keyframe sampling into Gemini Flash Vision         │
       │   • Tracks speaker horizontal center cx(t) trajectory  │
       │   • Instant cut on camera shot switches (Δcx >= 0.12)  │
       │   • Hermite smoothstep easing (3p²-2p³) on pacing/walk │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   ✂️ Step 4: Video Compositor (FFmpeg)                 │
       │   • 9:16 vertical crop + dynamic pan translation       │
       │   • Kinetic karaoke subtitles (.ASS) or modern clean   │
       │   • High-CTR top hook banner + speaker badge overlay   │
       │   • 80ms audio micro-fade & -14 LUFS loudness mastering│
       │   • Dedicated 1080x1920 cover image export             │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   📅 Step 5: GoHighLevel Publishing (ghl_publisher.py) │
       │   • Round-robin speaker interleaving (anti-fatigue)    │
       │   • Formats GHL Social Planner batch upload CSV        │
       │   • Exports companion metadata & virality review report│
       └────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Engineering Features

### 1. Smart Multi-Point Auto-Framing ([`core/compositor.py`](core/compositor.py))
* Solves the common problem where speakers walk across a stage or multi-camera switches push the speaker off-screen.
* Samples 3–7 keyframes across the clip into **Gemini 3.8 Flash Vision** using 2D spatial bounding-box grounding.
* **Deadzone Filter ($\pm 6\%$)**: Keeps the camera steady during minor head or body gestures to prevent jitter.
* **Director Cut Detection**: Sudden position changes ($\ge 0.12$) trigger an instantaneous broadcast cut.
* **Cinematic Stage Easing**: Gradual walking uses cubic Hermite smoothstep interpolation over 1.2s.

### 2. Speech-Onset Snapping & Acoustic Cushions ([`core/subtitles.py`](core/subtitles.py))
* Eliminates clipped first words and abrupt audio pops.
* Matches the LLM's `spoken_opening` against true VTT word cues to identify the exact phonetic start time.
* Applies a `0.35s` room-tone pre-roll cushion (clamped to prior sentence end) and `0.35s` lead-out.
* Mastered with an 80ms micro-fade-in (`afade=t=in:st=0:d=0.08`), 80Hz rumble high-pass, and **-14 LUFS** broadcast loudness normalization.

### 3. Kinetic Karaoke Subtitles & AI Polishing
* Automatically fixes speech-to-text misspellings, technical jargon, proper nouns, and verbal stumbles using Gemini.
* Generates stylized `.ASS` subtitles positioned within social media safe zones (avoiding TikTok/Reels UI overlay buttons).

### 4. Campaign Scheduling & Anti-Fatigue Interleaving ([`integrations/ghl_publisher.py`](integrations/ghl_publisher.py))
* Automatically interleaves clips across multiple speakers and topics so consecutive posts never repeat the same angle or speaker.
* Directly outputs CSV files compatible with **GoHighLevel (GHL) > Marketing > Social Planner** batch CSV import.

---

## 📋 Repository Structure

```
AIClipCutter/
├── README.md                      # Project documentation
├── LICENSE                        # MIT License
├── requirements.txt               # Python package dependencies
├── .env.example                   # Environment variable template
├── run_single.py                  # Single video CLI runner
├── run_batch.py                   # Batch playlist orchestrator & GHL mixer
├── core/
│   ├── gemini_extractor.py        # Gemini 3.8 Flash viral moment detection
│   ├── subtitles.py               # VTT speech snapping & .ASS subtitle generator
│   └── compositor.py              # Smart auto-framing & FFmpeg video compositor
├── integrations/
│   └── ghl_publisher.py           # GoHighLevel Social Planner scheduler
├── config/
│   ├── tedx.yaml                  # Conference / TEDx style preset
│   ├── linkedin.yaml              # Executive B2B thought-leadership preset
│   ├── miriam.yaml                # Keynote / Personal growth preset
│   └── playlist_tedx.json         # Example playlist catalog
├── scripts/
│   ├── launch_batch_vm.py         # On-demand GCP GPU VM launcher
│   └── setup_gcp_vm.sh            # GCE VM Ubuntu startup script
└── output/                        # Rendered MP4 clips, CSVs & subtitles
```

---

## 🛠️ Prerequisites & Installation

### 1. System Requirements
* **Python 3.10+**
* **FFmpeg**: Must be installed and accessible on your system `PATH`.
  * **Windows**: `winget install Gyan.FFmpeg` or `choco install ffmpeg`
  * **macOS**: `brew install ffmpeg`
  * **Ubuntu/Debian**: `sudo apt update && sudo apt install -y ffmpeg`
* Verify FFmpeg installation:
  ```bash
  ffmpeg -version
  ```

### 2. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/AIClipCutter.git
cd AIClipCutter

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Configuration & Authentication

AIClipCutter uses **Google Gemini 3.8 Flash** via Vertex AI.

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Configure your credentials:
   * **Option A (Recommended): Service Account Key**
     * Place your GCP Service Account JSON key at `config/gcp_service_account_key.json` (or set `GOOGLE_APPLICATION_CREDENTIALS` to its path).
     * Ensure the service account has the **Vertex AI User** role (`roles/aiplatform.user`).
     * AIClipCutter automatically detects your Project ID from the key file!
   * **Option B: Environment Variables**
     ```bash
     export GCP_PROJECT_ID="your-gcp-project-id"
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
     ```

---

## 🚀 Usage Guide

### 1. Process a Single Video
```bash
# Full end-to-end processing (Download -> Moments -> Render -> GHL CSV)
python run_single.py --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --preset config/tedx.yaml

# Re-render vertical clips with updated framing or timing
python run_single.py --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --step render --force

# Extract viral moments only (creates moments.json for review before rendering)
python run_single.py --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --step moments
```

### 2. Batch Process a Playlist Catalog
```bash
# Process all videos in a playlist catalog using a preset
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml

# Filter by custom virality score threshold (e.g. only clips scoring >= 90/100)
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml --min-virality 90

# Schedule drip campaign across custom date window
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml --start-date 2026-10-01 --end-date 2026-12-31
```

### 3. Pipeline Steps (`--step`)
You can execute individual pipeline stages independently:
* `download`: Download source video and auto-captions via `yt-dlp`.
* `moments`: Query Gemini 3.8 Flash to identify viral moments and output `moments.json`.
* `render`: Perform smart multi-point reframing, subtitles, and FFmpeg video rendering.
* `ghl`: Generate GoHighLevel Social Planner schedule CSV and companion review report.
* `all`: Execute the complete end-to-end pipeline (default).

---

## 🎨 Campaign Presets

AIClipCutter includes production-tested presets in `config/`:

| Preset | Target Platform | Subtitle Style | Focus & Narrative Angles |
| :--- | :--- | :--- | :--- |
| **`config/tedx.yaml`** | Instagram Reels / TikTok | Kinetic Hormozi | Epiphanies, emotional hooks, tickets/event CTA |
| **`config/linkedin.yaml`** | LinkedIn | Clean Modern | Contrarian reframes, B2B architecture, executive debate |
| **`config/miriam.yaml`** | Instagram Reels | Kinetic Hormozi | Personal growth, mindset shifts, authentic transformation |

### Creating Your Own Custom Preset
Create a new YAML file in `config/my_brand.yaml`:
```yaml
preset_name: "my_brand"
display_name: "Tech Podcast Clips"
target_platform: "instagram_reels"
gemini_model: "gemini-3.8-flash"
temperature: 0.75

# Virality & Duration Constraints
min_virality_score: 85
max_clips_per_video: 6
min_duration_seconds: 15
max_duration_seconds: 30

# Visual Styling
hook_duration_seconds: 2.5
font_style: "HORMOZI"
words_per_subtitle: 4

# Custom System Prompt for Gemini Moment Hunting
gemini_prompt: |
  You are an expert short-form video editor.
  Identify all high-impact viral moments scoring {min_virality_score}/100 or higher
  (between {min_duration} and {max_duration} seconds).
  ...
```

---

## 📄 Output Artifacts

All outputs are saved cleanly in the `output/` directory (gitignored):
* `output/<video_id>/clips/clip_1.mp4`: Final vertical 9:16 clip ready to publish.
* `output/<video_id>/clips/cover_1.jpg`: High-resolution 1080x1920 video cover image.
* `output/<video_id>/moments.json`: Raw Gemini moment detection data and virality scores.
* `output/ghl_master_playlist_schedule.csv`: GoHighLevel Social Planner batch upload CSV.
* `output/ghl_master_playlist_schedule_metadata_report.csv`: Complete campaign tracking spreadsheet with captions, hashtags, and scores.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
