# AIClipCutter 🎬⚡
> **Autonomous Long-to-Short Video Repurposing Pipeline powered by Google Cloud & AI**

AIClipCutter transforms 10–20 minute long-form YouTube videos into high-retention, viral 10–20 second vertical clips formatted and scheduled directly for **Instagram Reels** and **LinkedIn** via **GoHighLevel (GHL)**.

---

## 🎯 Target Campaigns

### 1. TEDx Glenbeigh 2027 (Instagram Reels / TikTok)
* **Objective:** Extract provocative, inspiring soundbites from TEDx Glenbeigh talks to hype the **TEDx Glenbeigh 2027** event.
* **Format:** 9:16 vertical video with dynamic speaker tracking and camera shot reframing.
* **Styling:** Kinetic karaoke subtitles (Hormozi style) + hook banner headline across the first 3 seconds.
* **Copy & CTA:** Inspiring post copy + call-to-action driving registrations to the TEDx Glenbeigh 2027 ticket waitlist + viral hashtags.
* **Preset:** `config/tedx.yaml`

### 2. Markus Schmidberger's Keynotes & Podcasts (LinkedIn)
* **Objective:** Extract tactical business frameworks, contrarian leadership opinions, and executive takeaways.
* **Format:** 9:16 vertical video with speaker tracking or split-screen layouts.
* **Styling:** Clean, modern typography without clutter.
* **Copy & CTA:** Thought-leadership scannable format with 1-line paragraphs, an open discussion question, and professional tags.
* **Preset:** `config/linkedin.yaml`

---

## 🏗️ Architecture & How It Works

AIClipCutter runs an ultra-fast, native Python pipeline powered by **Google Gemini 3.8 Flash** via Vertex AI and **FFmpeg**:

```
                       [ Long-Form YouTube Video ]
                                    │
                                    ▼
                     yt-dlp (Video & VTT Auto-Captions)
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   🧠 Step 1: AI Moment Hunter (Google Gemini 3.8 Flash) │
       │   • Evaluates virality (0-100 score)                   │
       │   • Enforces 10-20s duration constraint                │
       │   • Assigns distinct creative content angles           │
       │   • Generates platform-tailored captions & CTAs        │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   ⏱️ Step 2: Speech-Onset Snapping (core/subtitles.py)   │
       │   • Snaps LLM timestamps to exact VTT speech onset     │
       │   • Adds +0.35s acoustic pre-roll room-tone cushion    │
       │   • Completely eliminates truncated initial words      │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   🎯 Step 3: Smart Auto-Framing (core/compositor.py)   │
       │   • Samples frames across clip into Gemini Flash Vision│
       │   • Generates speaker trajectory cx(t)                 │
       │   • Instant cut on camera shot switches                │
       │   • Smoothstep easing (3p²-2p³) for pacing/walking     │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   ✂️ Step 4: Video Compositor (FFmpeg)                 │
       │   • 9:16 crop + dynamic translation filter             │
       │   • Hormozi-style .ASS kinetic karaoke subtitles       │
       │   • Top hook headline banner                           │
       │   • 80ms broadcast audio fade-in & -14 LUFS loudness   │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │   📅 Step 5: GoHighLevel Publishing (ghl_publisher.py) │
       │   • Mixed round-robin speaker schedule (anti-fatigue)  │
       │   • Prepares master folder: output/ghl_master_clips/   │
       │   • Generates GHL-ready CSV & metadata review report   │
       └────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Engineering Features

### 1. Smart Multi-Point Auto-Framing ([`core/compositor.py`](file:///c:/GitDev/AIClipCutter/core/compositor.py))
- Resolves the issue where speakers walk across the stage or camera angle changes push the speaker off-screen.
- Uses Gemini 3.8 Flash Vision to track the speaker's horizontal center $c_x(t)$ across 5–7 sampled frames.
- **Deadzone Filter ($\pm 6\%$)**: Small movements keep the camera 100% static to prevent jitter.
- **Director Cut Detection**: Sudden changes ($\ge 0.12$) trigger an instantaneous broadcast cut.
- **Stage Walking Easing**: Gradual movement uses cubic Hermite smoothstep easing over 1.2s.

### 2. Speech-Onset Snapping & Acoustic Cushions ([`core/subtitles.py`](file:///c:/GitDev/AIClipCutter/core/subtitles.py))
- Eliminates clipped first words and transient pops.
- Matches Gemini's `spoken_opening` against true VTT word cues to find exact phonetic onset.
- Applies a `0.35s` room-tone pre-roll cushion (clamped to prior sentence end) and `0.35s` lead-out.
- Applies an 80ms audio micro-fade-in (`afade=t=in:st=0:d=0.08`).

### 3. Campaign Calendar Scheduling & Interleaving ([`integrations/ghl_publisher.py`](file:///c:/GitDev/AIClipCutter/integrations/ghl_publisher.py))
- Automatically interleaves speakers in a round-robin rotation to avoid audience fatigue.
- Generates [`output/ghl_master_playlist_schedule.csv`](file:///c:/GitDev/AIClipCutter/output/ghl_master_playlist_schedule.csv) ready for direct CSV upload into **GoHighLevel > Marketing > Social Planner**.
- Compiles [`output/clips_metadata_report.csv`](file:///c:/GitDev/AIClipCutter/output/clips_metadata_report.csv) linking virality scores, hooks, captions, and file paths.

---

## 📋 Repository Structure

```
AIClipCutter/
├── README.md                      # Project documentation (this file)
├── PROJECT_PLAN.md                # Comprehensive roadmap & architecture
├── run_single.py                  # Single video CLI runner
├── run_batch.py                   # Batch playlist orchestrator & GHL mixer
├── core/
│   ├── gemini_extractor.py        # Gemini 3.8 Flash viral moment detection
│   ├── subtitles.py               # VTT speech snapping & .ASS subtitle generator
│   └── compositor.py              # Smart auto-framing & FFmpeg video compositor
├── integrations/
│   └── ghl_publisher.py           # GoHighLevel Social Planner scheduler
├── config/
│   ├── tedx.yaml                  # TEDx Glenbeigh prompt, styling & hashtags
│   ├── linkedin.yaml              # LinkedIn thought-leadership preset
│   ├── playlist_tedx.json         # TEDx Glenbeigh talks catalog
│   └── playlist_markus.json       # Markus Schmidberger video catalog
├── output/
│   ├── ghl_master_clips/          # Sequentially numbered MP4 clips & JPG covers
│   ├── ghl_master_playlist_schedule.csv # GoHighLevel Social Planner upload CSV
│   └── clips_metadata_report.csv  # Detailed tracking and review report
```

---

## 🚀 Usage Guide

### 1. Process a Single Video
```bash
# Run full pipeline for a TEDx talk
python run_single.py --url "https://www.youtube.com/watch?v=8pUxo0CZw5w" --preset config/tedx.yaml

# Re-render clips with updated framing or timing
python run_single.py --url "https://www.youtube.com/watch?v=8pUxo0CZw5w" --step render --force
```

### 2. Batch Process a Playlist & Create Master GHL Schedule
```bash
# Process TEDx Glenbeigh talks playlist
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml

# Process with custom virality threshold (e.g. >= 88%)
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml --min-virality 88

# Process Markus Schmidberger LinkedIn playlist
python run_batch.py --playlist config/playlist_markus.json --preset config/linkedin.yaml
```

### 3. Pipeline Steps (`--step`)
You can execute individual steps using `--step`:
- `download`: Download source video and auto-captions via `yt-dlp`.
- `moments`: Query Gemini 3.8 Flash to find viral moments (`moments.json`).
- `render`: Cut, reframing, subtitles, and FFmpeg video rendering.
- `ghl`: Generate GoHighLevel Social Planner CSV.
- `all`: Execute the complete end-to-end pipeline (default).
