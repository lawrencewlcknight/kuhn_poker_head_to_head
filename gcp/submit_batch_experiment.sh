#!/usr/bin/env bash
set -euo pipefail

# Submit a Google Cloud Batch job for the Kuhn poker head-to-head repo.
#
# Required environment variables:
#   PROJECT_ID
#   REGION
#   BUCKET
#   SA_EMAIL
#
# Optional environment variables:
#   SOURCE_REPO_URL              default: lawrencewlcknight head-to-head repo
#   SOURCE_REF                   default: main
#   DEEP_CFR_REPO_URL            default: lawrencewlcknight Kuhn Deep CFR repo
#   DREAM_REPO_URL               default: lawrencewlcknight Kuhn DREAM repo
#   ESCHER_REPO_URL              default: lawrencewlcknight Kuhn ESCHER repo
#   DEEP_CFR_REF                 default: SOURCE_REF
#   DREAM_REF                    default: SOURCE_REF
#   ESCHER_REF                   default: SOURCE_REF
#   HEAD_TO_HEAD_SUBDIR          default: kuhn_poker_head_to_head
#   BOOT_DISK_GB                 default: 100
#   PERIODIC_UPLOAD_SECONDS      default: 1800
#
# Usage:
#   ./gcp/submit_batch_experiment.sh JOB_NAME "PYTHON_COMMAND" MACHINE_TYPE MAX_RUN_SECONDS CPU_MILLI MEMORY_MIB

JOB_NAME="$1"
EXPERIMENT_COMMAND="$2"
MACHINE_TYPE="${3:-n2-standard-8}"
MAX_RUN_SECONDS="${4:-86400}"
CPU_MILLI="${5:-8000}"
MEMORY_MIB="${6:-32000}"

: "${PROJECT_ID:?Set PROJECT_ID first}"
: "${REGION:?Set REGION first}"
: "${BUCKET:?Set BUCKET first}"
: "${SA_EMAIL:?Set SA_EMAIL first}"

SOURCE_REPO_URL="${SOURCE_REPO_URL:-https://github.com/lawrencewlcknight/kuhn_poker_head_to_head.git}"
case "$SOURCE_REPO_URL" in
  *your-org*|*YOUR_*|*example.com*)
    echo "ERROR: SOURCE_REPO_URL is still a placeholder: $SOURCE_REPO_URL" >&2
    echo "Set it to the real head-to-head repo URL before submitting." >&2
    exit 2
    ;;
esac

SOURCE_REF="${SOURCE_REF:-main}"
DEEP_CFR_REPO_URL="${DEEP_CFR_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-deep-cfr-experiments}"
DREAM_REPO_URL="${DREAM_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-dream-experiments}"
ESCHER_REPO_URL="${ESCHER_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-escher-experiments}"
DEEP_CFR_REF="${DEEP_CFR_REF:-$SOURCE_REF}"
DREAM_REF="${DREAM_REF:-$SOURCE_REF}"
ESCHER_REF="${ESCHER_REF:-$SOURCE_REF}"
HEAD_TO_HEAD_SUBDIR="${HEAD_TO_HEAD_SUBDIR:-kuhn_poker_head_to_head}"
BOOT_DISK_GB="${BOOT_DISK_GB:-100}"
PERIODIC_UPLOAD_SECONDS="${PERIODIC_UPLOAD_SECONDS:-1800}"

JOB_JSON="$(mktemp "/tmp/${JOB_NAME}.XXXXXX.json")"

export JOB_NAME
export EXPERIMENT_COMMAND
export MACHINE_TYPE
export MAX_RUN_SECONDS
export CPU_MILLI
export MEMORY_MIB
export BUCKET
export SA_EMAIL
export SOURCE_REPO_URL
export SOURCE_REF
export DEEP_CFR_REPO_URL
export DREAM_REPO_URL
export ESCHER_REPO_URL
export DEEP_CFR_REF
export DREAM_REF
export ESCHER_REF
export HEAD_TO_HEAD_SUBDIR
export BOOT_DISK_GB
export PERIODIC_UPLOAD_SECONDS
export JOB_JSON

python3 <<'PY'
import json
import os
import shlex

job_json_path = os.environ["JOB_JSON"]
job_name = os.environ["JOB_NAME"]
experiment_command = os.environ["EXPERIMENT_COMMAND"]
experiment_command_literal = shlex.quote(experiment_command)
machine_type = os.environ["MACHINE_TYPE"]
max_run_seconds = os.environ["MAX_RUN_SECONDS"]
cpu_milli = int(os.environ["CPU_MILLI"])
memory_mib = int(os.environ["MEMORY_MIB"])
bucket = os.environ["BUCKET"]
service_account = os.environ["SA_EMAIL"]
source_repo_url = os.environ["SOURCE_REPO_URL"]
source_ref = os.environ["SOURCE_REF"]
deep_cfr_repo_url = os.environ["DEEP_CFR_REPO_URL"]
dream_repo_url = os.environ["DREAM_REPO_URL"]
escher_repo_url = os.environ["ESCHER_REPO_URL"]
deep_cfr_ref = os.environ["DEEP_CFR_REF"]
dream_ref = os.environ["DREAM_REF"]
escher_ref = os.environ["ESCHER_REF"]
head_to_head_subdir = os.environ["HEAD_TO_HEAD_SUBDIR"]
boot_disk_gb = int(os.environ["BOOT_DISK_GB"])
periodic_upload_seconds = int(os.environ["PERIODIC_UPLOAD_SECONDS"])

script = f"""#!/usr/bin/env bash
set -Euxo pipefail

export DEBIAN_FRONTEND=noninteractive
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export CUDA_VISIBLE_DEVICES=""
export TF_CPP_MIN_LOG_LEVEL=3
export ABSL_MIN_LOG_LEVEL=3
EXPERIMENT_COMMAND={experiment_command_literal}

echo "Starting job: {job_name}"
echo "Experiment command: $EXPERIMENT_COMMAND"

if command -v sudo >/dev/null 2>&1; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO apt-get update
$SUDO apt-get install -y git python3.9 python3.9-dev python3.9-venv python3-pip build-essential time

WORKDIR=/workspace
WORKSPACE_ROOT="$WORKDIR/deep_cfr_v3"
VENV_DIR="/tmp/kuhn-h2h-venv"
UPLOAD_DEST="{bucket}/{job_name}"
BOOTSTRAP_LOG="$WORKDIR/{job_name}_bootstrap.log"
PERIODIC_UPLOAD_SECONDS="{periodic_upload_seconds}"
PERIODIC_UPLOAD_PID=""
mkdir -p "$WORKSPACE_ROOT"

exec > >(tee -a "$BOOTSTRAP_LOG") 2>&1

upload_outputs() {{
  STATUS="$?"
  set +e
  if [ -n "$PERIODIC_UPLOAD_PID" ]; then
    kill "$PERIODIC_UPLOAD_PID" >/dev/null 2>&1 || true
    wait "$PERIODIC_UPLOAD_PID" >/dev/null 2>&1 || true
  fi
  if [ -d "$WORKSPACE_ROOT/{head_to_head_subdir}" ]; then
    cd "$WORKSPACE_ROOT/{head_to_head_subdir}"
    mkdir -p outputs
    cp "$BOOTSTRAP_LOG" outputs/bootstrap.log 2>/dev/null || true
    cp batch_run.log outputs/batch_run.log 2>/dev/null || true
    printf '{{"job_name": "{job_name}", "exit_status": %s}}\n' "$STATUS" > outputs/batch_status.json
    if [ -x "$VENV_DIR/bin/python" ] && [ -f scripts/upload_outputs_to_gcs.py ]; then
      "$VENV_DIR/bin/python" scripts/upload_outputs_to_gcs.py outputs "$UPLOAD_DEST/" || true
    else
      echo "Upload skipped because venv or uploader script is unavailable."
    fi
  fi
  trap - EXIT
  exit "$STATUS"
}}
trap upload_outputs EXIT

start_periodic_upload() {{
  (
    while true; do
      sleep "$PERIODIC_UPLOAD_SECONDS"
      if [ -d "$WORKSPACE_ROOT/{head_to_head_subdir}/outputs" ] && [ -x "$VENV_DIR/bin/python" ]; then
        echo "Periodic upload at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        cd "$WORKSPACE_ROOT/{head_to_head_subdir}"
        "$VENV_DIR/bin/python" scripts/upload_outputs_to_gcs.py outputs "$UPLOAD_DEST/" || true
      fi
    done
  ) &
  PERIODIC_UPLOAD_PID="$!"
  echo "Started periodic output upload with PID $PERIODIC_UPLOAD_PID"
}}

cd "$WORKSPACE_ROOT"

git clone --depth 1 --branch "{source_ref}" "{source_repo_url}" "{head_to_head_subdir}"
mkdir -p kuhn_poker_deep_cfr kuhn_poker_dream kuhn_poker_escher
git clone --depth 1 --branch "{deep_cfr_ref}" "{deep_cfr_repo_url}" kuhn_poker_deep_cfr/kuhn-poker-deep-cfr-experiments
git clone --depth 1 --branch "{dream_ref}" "{dream_repo_url}" kuhn_poker_dream/kuhn-poker-dream-experiments
git clone --depth 1 --branch "{escher_ref}" "{escher_repo_url}" kuhn_poker_escher/kuhn-poker-escher-experiments

find "$WORKSPACE_ROOT" -maxdepth 3 -type d | sort

cd "{head_to_head_subdir}"

export HOME="${{HOME:-/root}}"
export TMPDIR="/tmp"
export PIP_CACHE_DIR="/tmp/pip-cache"
export MPLCONFIGDIR="/tmp/matplotlib-cache"
export PATH="/usr/local/bin:$PATH"

mkdir -p "$HOME" "$TMPDIR" "$PIP_CACHE_DIR" "$MPLCONFIGDIR"

echo "Python version:"
python3.9 --version

echo "Machine information:"
nproc || true
free -h || true
df -h || true
lscpu | head -30 || true

python3.9 -m venv --copies "$VENV_DIR"
. "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-cache-dir --no-build-isolation -r requirements.txt
python -m pip install --no-cache-dir --no-build-isolation --no-deps -e .
python -m pip check || true

mkdir -p outputs/cloud
start_periodic_upload

bash -o pipefail -c "$EXPERIMENT_COMMAND" 2>&1 | tee batch_run.log

echo "Experiment completed successfully."
"""

job = {
    "taskGroups": [
        {
            "taskSpec": {
                "runnables": [
                    {
                        "script": {
                            "text": script,
                        },
                    },
                ],
                "computeResource": {
                    "cpuMilli": cpu_milli,
                    "memoryMib": memory_mib,
                },
                "maxRetryCount": 0,
                "maxRunDuration": f"{max_run_seconds}s",
            },
            "taskCount": 1,
            "parallelism": 1,
        },
    ],
    "allocationPolicy": {
        "instances": [
            {
                "policy": {
                    "machineType": machine_type,
                    "provisioningModel": "STANDARD",
                    "bootDisk": {
                        "sizeGb": boot_disk_gb,
                        "type": "pd-balanced",
                    },
                },
            },
        ],
        "serviceAccount": {
            "email": service_account,
        },
    },
    "logsPolicy": {
        "destination": "CLOUD_LOGGING",
    },
}

with open(job_json_path, "w", encoding="utf-8") as f:
    json.dump(job, f, indent=2)
PY

echo "Submitting Batch job from JSON: $JOB_JSON"
gcloud batch jobs submit "$JOB_NAME" \
  --location "$REGION" \
  --config "$JOB_JSON"

echo "Submitted job: $JOB_NAME"
