"""
Launch On-Demand Google Compute Engine (GCE) Batch Worker.
Spins up an ephemeral GPU VM on Google Cloud, executes the clipping batch,
uploads the outputs to Cloud Storage, and auto-terminates.
"""

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ID = "aiclipcutter-batch-7821"
DEFAULT_ZONE = "europe-west1-b"
DEFAULT_MACHINE_TYPE = "c2-standard-8"  # High compute (8 vCPUs) out-of-the-box, or g2-standard-4 for L4 GPU
BUCKET_NAME = "aiclipcutter-media-7821"


def launch_vm(
    zone: str = DEFAULT_ZONE,
    machine_type: str = DEFAULT_MACHINE_TYPE,
    vm_name: str = "aiclipcutter-worker",
    dry_run: bool = False
):
    startup_script = Path("scripts/setup_gcp_vm.sh").resolve()
    
    cmd = [
        "gcloud", "compute", "instances", "create", vm_name,
        f"--project={PROJECT_ID}",
        f"--zone={zone}",
        f"--machine-type={machine_type}",
        "--image-family=ubuntu-2204-lts",
        "--image-project=ubuntu-os-cloud",
        "--boot-disk-size=100GB",
        "--boot-disk-type=pd-ssd",
        "--scopes=cloud-platform",
        f"--service-account=aiclipcutter-sa@{PROJECT_ID}.iam.gserviceaccount.com",
        f"--metadata-from-file=startup-script={startup_script}"
    ]

    print("=" * 60)
    print(f"Launching On-Demand Google Cloud VM [{vm_name}]")
    print(f"Project:      {PROJECT_ID}")
    print(f"Zone:         {zone}")
    print(f"Machine Type: {machine_type}")
    print(f"Auto-Shutdown: Enabled (VM powers off when batch completes)")
    print("=" * 60)
    print("Command:\n" + " ".join(cmd))
    print("=" * 60)

    if dry_run:
        print("[Dry Run] Command prepared but not executed.")
        return

    print("Executing deployment...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("VM launched successfully! Monitoring logs...")
        print(f"To tail logs in real time, run:\n  gcloud compute instances get-serial-port-output {vm_name} --zone={zone} --project={PROJECT_ID}")
    else:
        print(f"Error launching VM:\n{result.stderr}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch on-demand GCE batch worker")
    parser.add_argument("--zone", default=DEFAULT_ZONE, help="GCP compute zone")
    parser.add_argument("--machine-type", default=DEFAULT_MACHINE_TYPE, help="GCP machine type")
    parser.add_argument("--vm-name", default="aiclipcutter-worker", help="Instance name")
    parser.add_argument("--dry-run", action="store_true", help="Print command without creating instance")
    args = parser.parse_args()

    launch_vm(
        zone=args.zone,
        machine_type=args.machine_type,
        vm_name=args.vm_name,
        dry_run=args.dry_run
    )

