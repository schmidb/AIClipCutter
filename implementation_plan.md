# AIClipCutter — Implementation Plan

Transform long-form YouTube videos (10–15 min each) into 50–70 high-retention 10–20 second clips formatted for **TEDx Glenbeigh 2027** (Instagram Reels) and **Markus's Keynotes** (LinkedIn), automated with **GoHighLevel (GHL) Social Planner** and powered 100% by **Google Cloud credits**.

---

## 🏗️ Core Engine: `NaufalRizqullah/opensource-clipping`

The entire video cutting, reframing, and rendering engine is powered by **`NaufalRizqullah/opensource-clipping`**, located inside [`engine/`](file:///c:/GitDev/AIClipCutter/engine/):
* **Face Tracking & 9:16 Auto-Centering:** Google MediaPipe BlazeFace & Ultralytics YOLOv8.
* **Kinetic Subtitles:** Dynamic `.ass` generator with Hormozi-style active word highlighting.
* **Hook V2:** Multi-hook flash/glitch teaser intro generator.
* **Customizations Added:** Dynamic 10–20s duration constraints (`--min-duration`, `--max-duration`), TEDx Glenbeigh 2027 and LinkedIn content presets (`--preset`), Google Cloud Vertex AI authentication, and automatic GoHighLevel Social Planner CSV export.

---

## 1. Execution Model: On-Demand Batch Processing

> [!IMPORTANT]
> **Zero Idle Costs**: The Google Cloud GPU instance is **ephemeral / on-demand**. 
> It starts up when a batch job is launched, processes the playlist, uploads the clips to cloud storage, outputs the GoHighLevel CSV, and **automatically shuts itself down** (`sudo poweroff` / `gcloud compute instances stop`). You only pay for the exact ~30–45 minutes of processing time!

---

## 2. Core Specifications & Presets

### A. Preset: `tedx` (Instagram Reels)
* **Target:** TEDx Glenbeigh talks (e.g. from the YouTube playlist).
* **AI Highlight Goal:** 10–20s mind-bending soundbites, counter-intuitive statements, emotional epiphanies.
* **Framing & Visuals:** 9:16 vertical crop with smooth stage-tracking (MediaPipe face tracking).
* **Subtitles:** Kinetic karaoke subtitles (`.ass`), Hormozi style (yellow/green word highlight, bold font, drop shadow).
* **Hook Banner:** Top headline displayed across seconds 0–3.
* **Copy & CTA:** Inspiring event hype copy + CTA driving registrations to the TEDx Glenbeigh 2027 waitlist + 15 viral hashtags.

### B. Preset: `linkedin` (Markus's Keynotes & Podcasts)
* **Target:** Markus's business talks, interviews, and podcasts.
* **AI Highlight Goal:** 15–30s tactical business frameworks, contrarian leadership opinions, practical advice.
* **Framing & Visuals:** 9:16 or 4:5 portrait; split-screen or camera-switching for multi-speaker podcasts.
* **Subtitles:** Clean, minimal modern typography.
* **Copy & CTA:** Scannable LinkedIn thought leadership post with short 1-line paragraphs, an open discussion question, and 3–5 professional tags.

---

## 3. GoHighLevel (GHL) Batch Publishing

* The pipeline automatically outputs `ghl_posts.csv` alongside the processed clips:
  * **Scheduled Date & Time:** Auto-spaced (e.g., 1 post per day at 9:00 AM or 6:00 PM).
  * **Social Accounts:** Mapped to Instagram Reels or LinkedIn.
  * **Post Content:** Pre-written hook, body text, CTA, and hashtags.
  * **Media URL:** Direct publicly-accessible URL hosted on Google Cloud Storage.
* **Publishing Step:** In GoHighLevel, navigate to **Marketing > Social Planner > CSV Upload**, select `ghl_posts.csv`, and all clips are scheduled in 30 seconds.

---

## 4. Google Cloud Setup & Architecture

1. **Dedicated Project:** Clean GCP project (e.g., `aiclipcutter-batch`).
2. **Billing Account:** Linked to your Google Cloud credits.
3. **APIs Enabled:**
   * Compute Engine API (`compute.googleapis.com`)
   * Vertex AI API (`aiplatform.googleapis.com`)
   * Cloud Storage API (`storage.googleapis.com`)
4. **Compute Instance:**
   * Machine: `g2-standard-4` (NVIDIA L4 GPU) or `n1-standard-4` (NVIDIA T4 GPU).
   * Boot Disk: Ubuntu 22.04 LTS (50–100 GB).
   * Startup script: Clones this repo, runs the batch command, and powers off on completion.

---

## 5. Verification & Quality Gates

1. **Playlist Inspection:** Verify all videos, durations, and download availability from the target playlist.
2. **Pilot Test (1 Video):**
   * Run 1 video from the playlist.
   * Verify face tracking, subtitle sync, 10–20s clip length, and copy generation.
   * Test GHL CSV import formatting.
3. **Full Batch Execution:**
   * Run all remaining playlist videos.
   * Validate that all clips and `ghl_posts.csv` are ready for scheduling.

