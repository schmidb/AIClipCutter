#!/bin/bash
# ==============================================================================
# AIClipCutter — Google Compute Engine (GCE) GPU VM Startup Script
# Automatically configures Ubuntu 22.04 LTS for GPU-accelerated video clipping.
# ==============================================================================

set -e
exec > >(tee -a /var/log/aiclipcutter-bootstrap.log) 2>&1

echo ">>> [1/5] Updating system packages..."
apt-get update && apt-get upgrade -y
apt-get install -y git curl wget ffmpeg python3-pip python3-venv

echo ">>> [2/5] Installing NVIDIA Drivers & CUDA (if GPU present)..."
if lspci | grep -i nvidia > /dev/null; then
    echo "NVIDIA GPU detected. Installing drivers..."
    apt-get install -y linux-headers-$(uname -r)
    apt-get install -y ubuntu-drivers-common
    ubuntu-drivers install --gpgpu
    nvidia-smi || true
else
    echo "No discrete GPU detected. Using high-efficiency CPU mode."
fi

echo ">>> [3/5] Setting up Python virtual environment..."
mkdir -p /opt/aiclipcutter
cd /opt/aiclipcutter

# Clone or sync AIClipCutter repository
# In production, git clone your repository or sync from GCS:
# gsutil cp -r gs://aiclipcutter-media-7821/code/* /opt/aiclipcutter/

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f "engine/requirements.txt" ]; then
    pip install -r engine/requirements.txt
fi
pip install google-genai faster-whisper mediapipe yt-dlp pyyaml

echo ">>> [4/5] Running Batch Clipping Job with OpenSource-Clipping Engine..."
python run_batch.py --playlist config/playlist_tedx.json --preset tedx

# Sync final clips and schedule to Cloud Storage
gsutil -m cp -r outputs/* gs://aiclipcutter-media-7821/clips/ || true
gsutil cp output/ghl_social_planner_schedule.csv gs://aiclipcutter-media-7821/ || true

echo ">>> [5/5] Batch processing complete. Automatically powering off VM..."
# Power off the VM to avoid burning unnecessary credits
poweroff

