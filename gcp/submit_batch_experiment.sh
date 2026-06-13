#!/usr/bin/env bash
set -euo pipefail

# Submit a Google Cloud Batch job for the Kuhn poker head-to-head repo.
#
# Required environment variables:
#   PROJECT_ID
#   REGION
#   BUCKET
#   SA_EMAIL
#   SOURCE_REPO_URL              head-to-head repo URL
#
# Optional environment variables:
#   SOURCE_REF                   default: main
#   DEEP_CFR_REPO_URL            default: lawrencewlcknight Kuhn Deep CFR repo
#   DREAM_REPO_URL               default: lawrencewlcknight Kuhn DREAM repo
#   ESCHER_REPO_URL              default: lawrencewlcknight Kuhn ESCHER repo
#   DEEP_CFR_REF                 default: SOURCE_REF
#   DREAM_REF                    default: SOURCE_REF
#   ESCHER_REF                   default: SOURCE_REF
#   HEAD_TO_HEAD_SUBDIR          default: kuhn_poker_head_to_head
#   BOOT_DISK_GB                 default: 100
#
# Usage:
#   ./gcp/submit_batch_experiment.sh JOB_NAME "PYTHON_COMMAND" MACHINE_TYPE MAX_RUN_SECONDS CPU_MILLI MEMORY_MIB

JOB_NAME="$1"
EXPERIMENT_COMMAND="$2"
MACHINE_TYPE="${3:-n2-standard-8}"
MAX_RUN_SECONDS="${4:-43200}"
CPU_MILLI="${5:-8000}"
MEMORY_MIB="${6:-32000}"

: "${PROJECT_ID:?Set PROJECT_ID first}"
: "${REGION:?Set REGION first}"
: "${BUCKET:?Set BUCKET first}"
: "${SA_EMAIL:?Set SA_EMAIL first}"
: "${SOURCE_REPO_URL:?Set SOURCE_REPO_URL first}"

SOURCE_REF="${SOURCE_REF:-main}"
DEEP_CFR_REPO_URL="${DEEP_CFR_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-deep-cfr-experiments}"
DREAM_REPO_URL="${DREAM_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-dream-experiments}"
ESCHER_REPO_URL="${ESCHER_REPO_URL:-https://github.com/lawrencewlcknight/kuhn-poker-escher-experiments}"
DEEP_CFR_REF="${DEEP_CFR_REF:-$SOURCE_REF}"
DREAM_REF="${DREAM_REF:-$SOURCE_REF}"
ESCHER_REF="${ESCHER_REF:-$SOURCE_REF}"
HEAD_TO_HEAD_SUBDIR="${HEAD_TO_HEAD_SUBDIR:-kuhn_poker_head_to_head}"
BOOT_DISK_GB="${BOOT_DISK_GB:-100}"

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
export JOB_JSON

python3 <<'PY'
import json
import os

job_json_path = os.environ["JOB_JSON"]
job_name = os.environ["JOB_NAME"]
experiment_command = os.environ["EXPERIMENT_COMMAND"]
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

script = f"""#!/usr/bin/env bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=""
export TF_CPP_MIN_LOG_LEVEL=3
export ABSL_MIN_LOG_LEVEL=3

echo "Starting job: {job_name}"
echo "Experiment command: {experiment_command}"

if command -v sudo >/dev/null 2>&1; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO apt-get update
$SUDO apt-get install -y git python3-pip python3-dev python3-venv rsync time

WORKDIR=/workspace
WORKSPACE_ROOT="$WORKDIR/deep_cfr_v3"
mkdir -p "$WORKSPACE_ROOT"
cd "$WORKSPACE_ROOT"

git clone --depth 1 --branch "{source_ref}" "{source_repo_url}" "{head_to_head_subdir}"
mkdir -p kuhn_poker_deep_cfr kuhn_poker_dream kuhn_poker_escher
git clone --depth 1 --branch "{deep_cfr_ref}" "{deep_cfr_repo_url}" kuhn_poker_deep_cfr/kuhn-poker-deep-cfr-experiments
git clone --depth 1 --branch "{dream_ref}" "{dream_repo_url}" kuhn_poker_dream/kuhn-poker-dream-experiments
git clone --depth 1 --branch "{escher_ref}" "{escher_repo_url}" kuhn_poker_escher/kuhn-poker-escher-experiments

find "$WORKSPACE_ROOT" -maxdepth 3 -type d | sort

cd "{head_to_head_subdir}"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .

mkdir -p outputs/cloud

set +e
/usr/bin/time -v bash -lc '{experiment_command}' 2>&1 | tee batch_run.log
STATUS="${{PIPESTATUS[0]}}"
set -e

cat > batch_status.json <<STATUS_JSON
{{"job_name": "{job_name}", "exit_status": ${{STATUS}}}}
STATUS_JSON

UPLOAD_DEST="{bucket}/{job_name}"
mkdir -p outputs
cp batch_run.log batch_status.json outputs/ || true
gsutil -m cp -r outputs "$UPLOAD_DEST/"

exit "$STATUS"
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
                    "bootDisk": {
                        "sizeGb": boot_disk_gb,
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
