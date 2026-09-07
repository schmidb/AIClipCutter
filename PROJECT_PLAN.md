# AIClipCutter — Comprehensive Implementation Plan & Architecture

This document outlines the end-to-end plan to build and deploy **AIClipCutter**, turning 10–15 minute YouTube videos into 10–20 second viral clips for **TEDx Glenbeigh 2027** (Instagram Reels) and **Markus's Keynotes/Podcasts** (LinkedIn), automated with **GoHighLevel (GHL)** and powered by **Google Cloud credits**.

---

## 1. Project Objectives & Metrics

| Metric | Target |
| :--- | :--- |
| **Input** | ~10 long-form YouTube videos (10–15 min each) |
| **Output Volume** | 5–7 clips per video (Total: 50–70 clips) |
| **Clip Duration** | Strictly 10–20 seconds (optimized for >100% loop completion rate) |
| **Aspect Ratios** | 9:16 (Instagram Reels & LinkedIn Mobile Video) or 4:5 (LinkedIn Feed) |
| **Cost to Run** | $0 out-of-pocket (100% funded via Google Cloud credits) |
| **Publishing Destination** | GoHighLevel Social Planner (automated calendar drip) + Google Drive |

---

## 2. Platform Preset Specifications

### A. Preset: `tedx` (Instagram Reels / TikTok)
* **Goal:** Create buzz, build audience anticipation, and drive ticket waitlist signups for **TEDx Glenbeigh 2027**.
* **Detection Criteria (Gemini Prompt):**
  * Mind-bending, counter-intuitive statements or epiphanies.
  * Emotionally charged stories with a self-contained 10–20s punchline.
  * Spoken words that start immediately with zero dead intro.
* **Visual Framing:**
  * 9:16 full-bleed vertical crop.
  * Smooth stage tracking (centering the speaker as they pace the TEDx red dot).
  * 3-second hook text banner at the top of the screen (e.g. *"Why 99% of people quit..."*).
* **Subtitle Styling:**
  * Kinetic dynamic karaoke (`.ass` format), Hormozi-style (bright yellow/green word highlights, bold font with drop shadow).
* **Social Copy Output:**
  * Hook line + 2-sentence emotional takeaway.
  * CTA: *"🎟️ TEDx Glenbeigh returns in 2027. Don't miss the talks that will shape the future. Tap the link in bio to join the priority ticket waitlist!"*
  * 12–15 high-reach hashtags (`#TEDx #TEDxGlenbeigh #IdeasWorthSpreading #Glenbeigh2027 ...`).

### B. Preset: `linkedin` (Markus's Keynotes & Podcasts)
* **Goal:** Thought leadership, executive networking, and engagement on Markus's LinkedIn profile.
* **Detection Criteria (Gemini Prompt):**
  * Practical business frameworks, leadership decisions, scaling lessons, or contrarian industry insights.
* **Visual Framing:**
  * Solo talk: 9:16 full vertical or 4:5 portrait.
  * Multi-speaker / Podcast: Dynamic split-screen (top/bottom) or camera-switching focused on the active speaker.
* **Subtitle Styling:**
  * Clean, minimal modern typography (white text, subtle box background or crisp outline, zero cartoonish animations).
* **Social Copy Output:**
  * Strong one-line hook headline.
  * Short, scannable paragraphs with plenty of white space.
  * Open-ended question at the end to stimulate comments and debate in the LinkedIn algorithm.
  * 3–5 targeted industry hashtags (`#Leadership #BusinessStrategy #ExecutiveCoaching ...`).

---

## 3. Google Cloud Architecture (Using Credits)

### A. Compute: GCE GPU VM
* **Machine Type:** `g2-standard-4` (equipped with 1x NVIDIA L4 GPU, 16 GB VRAM, 4 vCPUs, 16 GB RAM) or `n1-standard-4` (with NVIDIA T4 GPU).
* **Role:**
  * GPU-accelerated video download (`yt-dlp`).
  * GPU-accelerated speech-to-text (`faster-whisper` large-v3 via CUDA).
  * GPU-accelerated face detection (`MediaPipe` / `YOLOv8`).
  * GPU-accelerated video rendering & subtitle burning (`FFmpeg` using NVENC `h264_nvenc`).
* **Cost Efficiency:** A single 15-minute video processes in ~2–3 minutes on an L4 GPU. Processing all 10 videos will take under 45 minutes of VM runtime, consuming just a few dollars of your cloud credits.

### B. Intelligence: Google Vertex AI (Gemini 3.8 Flash)
* Gemini analyzes full transcripts with word timestamps.
* Generates structured JSON output with exact timestamps, hook headlines, virality scores, and platform-specific post descriptions.

### C. Storage & Delivery: Google Cloud Storage (GCS)
* Processed MP4 clips and metadata files are stored in a regional GCS bucket.
* Direct public or signed URLs are generated for ingestion into GoHighLevel.

---

## 4. GoHighLevel (GHL) Publishing Pipeline

### Workflow:
1. When clips are exported, the system generates:
   * `clip_01.mp4`, `clip_02.mp4`... uploaded to GCS.
   * `clip_metadata.json` containing the post text, media URL, and target platform.
   * `ghl_social_planner.csv` formatted according to GoHighLevel's CSV upload specification.
2. **Option A (Bulk CSV Upload):**
   * Download `ghl_social_planner.csv`.
   * In GoHighLevel: Navigate to **Marketing > Social Planner > CSV Upload**.
   * Map columns and schedule 50–70 posts across Instagram and LinkedIn over the next 30–60 days in one click.
3. **Option B (Direct REST API):**
   * Configure `GHL_API_KEY` and `GHL_LOCATION_ID`.
   * Pipeline automatically creates posts directly inside GHL Social Planner as **Drafts** or **Scheduled Posts**, ready for one-click approval.

---

## 5. Execution Roadmap

### Phase 1: Core Engine & Presets Customization
- Clone and modularize the clipping engine (leveraging `NaufalRizqullah/opensource-clipping`).
- Create `config/tedx.yaml` and `config/linkedin.yaml` containing the customized Gemini system prompts and subtitle styling parameters.
- Enforce strict 10–20 second window constraint on the Gemini highlight extractor.

### Phase 2: GoHighLevel & Cloud Storage Integrations
- Implement `integrations/gcs_uploader.py` to stream finished clips to a GCP bucket.
- Implement `integrations/ghl_scheduler.py` to produce GHL-compliant CSVs and/or trigger the GHL Social Planner REST API.

### Phase 3: GCP VM Setup & GPU Automation
- Create `scripts/setup_gcp_vm.sh` with automated installation of NVIDIA drivers, CUDA, FFmpeg with NVENC, and Python dependencies.
- Provide step-by-step instructions for launching the VM with Google Cloud credits via the Google Cloud Console or `gcloud` CLI.

### Phase 4: Batch Processing & Pilot Testing
- Test with 1 TEDx Glenbeigh talk and 1 Markus podcast talk.
- Review clip selection, pacing, 10–20s duration, visual framing, and generated captions.
- Run the full batch across all 10 videos and export the complete 60-post schedule into GoHighLevel.

