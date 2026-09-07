# AIClipCutter 🎬⚡
> **Autonomous Long-to-Short Video Repurposing Pipeline powered by Google Cloud & AI**

AIClipCutter transforms 10–15 minute long-form YouTube videos into high-retention, viral 10–20 second clips formatted and scheduled directly for **Instagram Reels** and **LinkedIn** via **GoHighLevel (GHL)**.

---

## 🎯 Target Use Cases

### 1. TEDx Glenbeigh 2027 (Instagram Reels / TikTok)
* **Objective:** Extract the most provocative, inspiring, and mind-bending soundbites from TEDx Glenbeigh talks to hype the **TEDx Glenbeigh 2027** event.
* **Format:** 9:16 vertical video with smooth stage tracking (following the speaker on the red dot).
* **Styling:** Kinetic karaoke subtitles (Hormozi style) + hook banner headline across the first 3 seconds.
* **Copy & CTA:** Inspiring caption + call-to-action driving registrations to the TEDx Glenbeigh 2027 waitlist/tickets + high-reach hashtags.

### 2. Markus's Podcasts & Keynotes (LinkedIn)
* **Objective:** Extract tactical business frameworks, contrarian leadership opinions, and executive takeaways.
* **Format:** 9:16 vertical or 4:5 portrait with active speaker tracking or split-screen podcast layouts.
* **Styling:** Clean, modern typography without distracting clutter.
* **Copy & CTA:** Thought-leadership scannable format (short 1-line paragraphs, strong opening hook, open discussion question, and 3–5 targeted industry tags).

---

## 🏗️ Architecture Overview

```
                      [ YouTube URLs / Local MP4s ]
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │    Google Cloud Engine VM    │
                   │    (NVIDIA GPU + Credits)    │
                   └──────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  faster-whisper │      │ Google Vertex AI│      │   MediaPipe /   │
│  (Word-level    │      │  Gemini 2.5/3   │      │     YOLOv8      │
│  Timestamps)    │      │ (Viral Moments) │      │  (Face Track)   │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │       FFmpeg Compositor      │
                   │  (9:16 Crop + ASS Subtitles  │
                   │   + Hook V2 Glitch Teasers)  │
                   └──────────────┬───────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │   Cloud Storage & GHL Sync   │
                   └──────────────┬───────────────┘
                                  │
                   ┌──────────────┴───────────────┐
                   ▼                              ▼
        [ Google Drive / GCS ]        [ GoHighLevel Social Planner ]
       (Backup & Mobile Review)       (Drip-scheduled 30–60 Day Queue)
                                                  │
                                                  ▼
                                       [ Auto-Publish to IG & IN ]
```

---

## ⚡ Tech Stack & Credits Utilization

* **AI Reasoning:** **Google Gemini 2.5 / 3.0** via Vertex AI API (identifies high-impact 10–20s moments, writes tailored copy, formats hooks).
* **Compute & Rendering:** **Google Compute Engine (GCE)** GPU VM (`g2-standard-4` with NVIDIA L4 or `n1-standard-4` with T4 GPU) — 100% funded with Google Cloud credits.
* **Speech-to-Text:** `faster-whisper` (CUDA-accelerated word-level alignment).
* **Vision & Re-framing:** Google MediaPipe BlazeFace / YOLOv8 for speaker centering.
* **Compositor:** FFmpeg with NVENC hardware acceleration.
* **Distribution:** GoHighLevel Social Planner API / CSV Bulk Scheduler + Google Drive backup.

---

## 📋 Repository Structure

```
AIClipCutter/
├── README.md               # Project overview & quickstart
├── PROJECT_PLAN.md         # Detailed phased execution roadmap
├── implementation_plan.md  # Architectural specification
├── run_batch.py            # Master CLI orchestrator
├── config/
│   ├── tedx.yaml           # TEDx Glenbeigh 2027 prompt & subtitle preset
│   ├── linkedin.yaml       # Markus LinkedIn prompt & styling preset
│   ├── playlist_tedx.json  # Catalog of all 8 TEDx Glenbeigh talks
│   └── gcp_service_account_key.json  # GCP Service Account (gitignored)
├── engine/                 # Core engine (powered by NaufalRizqullah/opensource-clipping)
│   ├── main.py             # OpenSource-clipping CLI entrypoint
│   ├── clipping/           # Face tracking, Hormozi .ASS subtitles, FFmpeg compositing
│   └── requirements.txt    # Engine dependencies (faster-whisper, mediapipe, ultralytics, etc.)
├── core/
│   └── gemini_extractor.py # Vertex AI Gemini highlight extractor
├── integrations/
│   └── ghl_publisher.py    # GoHighLevel Social Planner CSV generator
└── scripts/
    ├── setup_gcp_vm.sh     # Automation script to bootstrap GCE GPU VM
    └── launch_batch_vm.py  # On-demand GCP VM launcher
```

---

## 🚀 Quick Usage (CLI)

```bash
# Process TEDx Glenbeigh video (6 clips, 10-20s, IG Reels formatting)
python run_batch.py --url "https://youtube.com/watch?v=TEDX_ID" --preset tedx --clips 6

# Process Markus podcast (5 clips, LinkedIn formatting)
python run_batch.py --url "https://youtube.com/watch?v=PODCAST_ID" --preset linkedin --clips 5 --split-screen

# Batch process from a list of URLs and export to GoHighLevel
python run_batch.py --file urls.txt --export-ghl
```

