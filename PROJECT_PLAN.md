# AIClipCutter — Master Architecture & Project Roadmap

> **Autonomous Long-to-Short Video Repurposing Pipeline**  
> Transforms 10–20 minute YouTube videos into viral, high-retention 10–20 second vertical clips for **Instagram Reels** and **LinkedIn**, formatted and scheduled directly for **GoHighLevel (GHL) Social Planner**.

---

## 1. Executive Summary & Architecture Clarification

AIClipCutter runs on a unified, high-performance **Native Pipeline** centered in `core/`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AIClipCutter Architecture                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Production Native Pipeline                       │
│                                                                        │
│ • run_single.py & run_batch.py (Master CLI Entrypoints)                │
│ • core/gemini_extractor.py (Moment Hunting & Virality Scoring)         │
│ • core/compositor.py (Smart Multi-Point Vision Auto-Framing)           │
│ • core/subtitles.py (Acoustic Snapping & Kinetic Subtitles)            │
│ • integrations/ghl_publisher.py (GoHighLevel Social Planner Engine)    │
│ • Ultra-fast (15-30s render per clip, zero local CUDA/PyTorch bloat)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Production Tech Stack (Native Pipeline)

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Moment Hunter** | **Google Gemini 3.8 Flash** (Vertex AI) | Scans video transcript, scores virality (0–100), selects 10–20s moments, writes tailored captions. |
| **Speech Alignment** | **VTT Cue Parser + Pre-Roll Cushion** | Snaps LLM timestamps to exact syllable start + adds `0.35s` room-tone cushion to avoid truncated words. |
| **Auto-Framing** | **Gemini 3.8 Flash Multimodal Vision** | Samples 5–7 frames across clip, tracks speaker horizontal center $c_x(t)$, applies cinematic easing. |
| **Video Compositor** | **FFmpeg (Native Windows/Linux)** | 9:16 vertical crop, Hormozi-style `.ass` karaoke subtitles, 3s hook banner, 80ms audio micro-fade-in. |
| **Social Automation** | **GoHighLevel Social Planner Engine** | Auto-spaces posts, interleaves speakers (round-robin), formats captions, CTAs, and hashtags. |

---

## 3. Key Completed Milestones

- [x] **Acoustic Pre-Roll & Speech Snapping ([`core/subtitles.py`](file:///c:/GitDev/AIClipCutter/core/subtitles.py))**:
  - Eliminated hard audio cuts where first words were chopped in half.
  - Added `0.35s` room-tone lead-in and `0.35s` decay lead-out clamped to prior cue boundaries.
  - Added 80ms broadcast audio micro-fade-in (`afade=t=in:st=0:d=0.08`) and -14 LUFS loudness normalization.

- [x] **Smart Multi-Point Auto-Framing ([`core/compositor.py`](file:///c:/GitDev/AIClipCutter/core/compositor.py))**:
  - Eliminated issue where speakers paced out of the vertical frame or camera angles switched.
  - Multi-frame trajectory extraction via Gemini 3.8 Flash multimodal vision.
  - Deadzone filtering ($\pm 6\%$) prevents camera jitter.
  - Instant cut on camera shot switches ($\ge 0.12$ jump) and smoothstep S-curve ($3p^2 - 2p^3$) on stage walking.
  - Minimum hold guardrail ($\ge 3.2\text{s}$) prevents hyperactive cuts.

- [x] **GoHighLevel Campaign Scheduling & Interleaving ([`integrations/ghl_publisher.py`](file:///c:/GitDev/AIClipCutter/integrations/ghl_publisher.py))**:
  - Round-robin speaker mixing across batch playlists to avoid audience fatigue.
  - Calendar drip scheduling from Mid-September to Christmas (1 post/week every Tuesday at 6:00 PM).
  - Exported standalone master folder ([`output/ghl_master_clips/`](file:///c:/GitDev/AIClipCutter/output/ghl_master_clips/)) with sequentially numbered clips and cover images.

- [x] **Batch Pilot Processing (3 TEDx Talks Re-rendered)**:
  - Roser Bosch (`8pUxo0CZw5w`): 5 clips re-rendered with smart auto-framing.
  - Paul Byrne (`17ej8XgPpMs`): 5 clips re-rendered with smart auto-framing.
  - Nikolina Tijardovic (`1uaAfRhwuAQ`): 5 clips re-rendered with smart auto-framing.

---

## 4. Remaining Roadmap & Next Steps

### Phase 1: Complete TEDx Glenbeigh Playlist (5 Remaining Talks)
Process remaining talks from `config/playlist_tedx.json`:
1. `aWmH7t3sZbs` — Fiola Foley (*When Running Toward Yourself Is the Only Way Home*)
2. `-m8jIhQyiDY` — Patrick McKeown (*From Breathless to Breathe Less*)
3. `OKH_YOOEcdQ` — Miriam Schmidberger (*The Power of Giving Birth - to Yourself*)
4. `SOjzpKAPTzw` — Kenneth Keavey (*What is the true cost of cheap food?*)
5. `C7U9_rz6uyg` — Debbie Reynolds (*The data privacy revolution*)

### Phase 2: Dr. Markus Schmidberger LinkedIn Video Campaign
Process talks from `config/playlist_markus.json` using `--preset config/linkedin.yaml`:
1. `8nvuz0TV7tw` — Dr. Markus Schmidberger (Video 1)
2. `hvmkH2xUJ4k` — Dr. Markus Schmidberger (Video 2)
3. `jIas2vGSn2Q` — Dr. Markus Schmidberger (Video 3)
4. `BBdwxF5WKLQ` — Dr. Markus Schmidberger (Video 4)

### Phase 3: Virality Uncapping & Dynamic Capacity (Completed)
- [x] Implemented Option B: Unconstrained angle categorization with dynamic clip capacity (up to 10 clips per video) driven purely by virality score ($\ge 88\%$).

---

## 5. Repository Maintenance Decision
- **`PROJECT_PLAN.md`**: Maintained as the single, authoritative project roadmap and architecture document.
- **Unified Architecture**: The clean native `core/` pipeline is the sole, dedicated production system.
