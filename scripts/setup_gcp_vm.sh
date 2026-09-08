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
# gsutil cp -r gs://your-bucket-name/code/* /opt/aiclipcutter/

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ">>> [4/5] Running Batch Clipping Job with AIClipCutter Native Pipeline..."
python run_batch.py --playlist config/playlist_tedx.json --preset config/tedx.yaml

# Sync final clips and schedule to Cloud Storage (if GCS_BUCKET_NAME configured)
if [ -n "$GCS_BUCKET_NAME" ]; then
    echo "Syncing rendered clips to gs://${GCS_BUCKET_NAME}..."
    gsutil -m cp -r output/* "gs://${GCS_BUCKET_NAME}/clips/" || true
fi

echo ">>> [5/5] Batch processing complete. Automatically terminating VM..."
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{print $NF}' || echo "")
NAME=$(hostname)
if [ -n "$ZONE" ]; then
    gcloud compute instances delete "$NAME" --zone="$ZONE" --quiet || poweroff
else
    poweroff
fi

