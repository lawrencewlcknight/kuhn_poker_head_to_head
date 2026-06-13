# Running the Kuhn head-to-head experiment on Google Cloud Batch

This guide explains how to run the combined Kuhn poker head-to-head experiment
on Google Cloud using Google Batch. The workflow is designed to match the other
Kuhn experiment repositories:

1. configure Google Cloud locally;
2. create a Cloud Storage bucket for outputs;
3. create a service account for Batch jobs;
4. make the Batch submission helper executable;
5. run a smoke test;
6. run the full head-to-head experiment with configurable CPU and memory;
7. inspect logs and retrieve outputs.

Each Batch job creates a temporary VM, clones the source repository, creates an
isolated Python virtual environment, installs the head-to-head package, runs the
selected command, copies `outputs/` to Cloud Storage, and exits. Batch handles
VM lifecycle management, so there is no persistent VM to shut down after a
successful job.

Important: this lightweight repo imports solver and snapshot code from the
three sibling Kuhn repos. The Batch helper now clones those three repos
explicitly and builds this layout on the VM:

```text
deep_cfr_v3/
  kuhn_poker_deep_cfr/
  kuhn_poker_dream/
  kuhn_poker_escher/
  kuhn_poker_head_to_head/
```

Set `SOURCE_REPO_URL` to the remote for this head-to-head repository. The three
algorithm repository URLs default to:

- `https://github.com/lawrencewlcknight/kuhn-poker-deep-cfr-experiments`
- `https://github.com/lawrencewlcknight/kuhn-poker-dream-experiments`
- `https://github.com/lawrencewlcknight/kuhn-poker-escher-experiments`

---

## 1. Prerequisites

You need:

- a Google Cloud project with billing enabled;
- the Google Cloud CLI installed locally;
- permission to create service accounts, IAM bindings, Batch jobs, and Cloud
  Storage buckets;
- a Git repository available to the Batch VM for this head-to-head repo;
- network access from the Batch VM to the three Kuhn algorithm repos.

If the repository is private, adapt the clone step in
`gcp/submit_batch_experiment.sh` to use an authenticated method such as a deploy
key, GitHub token, or a pre-built container image.

---

## 2. One-time local Google Cloud setup

Authenticate and select your project:

```bash
gcloud init
gcloud auth login

export PROJECT_ID="your-gcp-project-id"
gcloud config set project "$PROJECT_ID"
```

For UK-based use, `europe-west1` is a sensible default region:

```bash
export REGION="europe-west1"
export ZONE="europe-west1-b"
```

Enable the required APIs:

```bash
gcloud services enable \
  compute.googleapis.com \
  batch.googleapis.com \
  logging.googleapis.com \
  storage.googleapis.com
```

---

## 3. Create a Cloud Storage bucket for outputs

Create a regional bucket in the same region as the Batch jobs:

```bash
export BUCKET_NAME="${PROJECT_ID}-kuhn-head-to-head-results"
export BUCKET="gs://${BUCKET_NAME}"

gcloud storage buckets create "$BUCKET" \
  --location="$REGION" \
  --uniform-bucket-level-access
```

Check the bucket exists:

```bash
gcloud storage buckets describe "$BUCKET"
```

---

## 4. Create a service account for Batch jobs

Create a dedicated service account:

```bash
export SA_NAME="kuhn-head-to-head-runner"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Kuhn poker head-to-head experiment runner" \
  --project="$PROJECT_ID"
```

Grant the service account permission to write logs:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

Grant the service account permission to report Batch agent status:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/batch.agentReporter"
```

Grant the service account permission to write outputs to the bucket:

```bash
gcloud storage buckets add-iam-policy-binding "$BUCKET" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"
```

Allow your user account to run jobs as this service account:

```bash
export YOUR_EMAIL="your-email@example.com"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="user:${YOUR_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

If you need to inspect logs from your local account, make sure your user has
log-viewing permission:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:${YOUR_EMAIL}" \
  --role="roles/logging.viewer"
```

---

## 5. Environment variables for each new terminal

Before submitting jobs from a new shell session, set:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west1"
export BUCKET="gs://${PROJECT_ID}-kuhn-head-to-head-results"
export SA_EMAIL="kuhn-head-to-head-runner@${PROJECT_ID}.iam.gserviceaccount.com"

# This is the default value used by gcp/submit_batch_experiment.sh.
# Set it explicitly if you want the terminal environment to be self-documenting
# or if you need to point at a fork.
export SOURCE_REPO_URL="https://github.com/lawrencewlcknight/kuhn_poker_head_to_head.git"
export SOURCE_REF="main"

# These are the default values used by gcp/submit_batch_experiment.sh.
# Set them explicitly if you want the terminal environment to be self-documenting
# or if you need to point at forks.
export DEEP_CFR_REPO_URL="https://github.com/lawrencewlcknight/kuhn-poker-deep-cfr-experiments"
export DREAM_REPO_URL="https://github.com/lawrencewlcknight/kuhn-poker-dream-experiments"
export ESCHER_REPO_URL="https://github.com/lawrencewlcknight/kuhn-poker-escher-experiments"
export DEEP_CFR_REF="$SOURCE_REF"
export DREAM_REF="$SOURCE_REF"
export ESCHER_REF="$SOURCE_REF"

export HEAD_TO_HEAD_SUBDIR="kuhn_poker_head_to_head"

gcloud config set project "$PROJECT_ID"
```

Check the values:

```bash
echo "$PROJECT_ID"
echo "$REGION"
echo "$BUCKET"
echo "$SA_EMAIL"
echo "$SOURCE_REPO_URL"
echo "$DEEP_CFR_REPO_URL"
echo "$DREAM_REPO_URL"
echo "$ESCHER_REPO_URL"
```

---

## 6. Prepare the submission helper

The repository includes the maintained helper:

```bash
gcp/submit_batch_experiment.sh
```

Make it executable and check its syntax:

```bash
chmod +x gcp/submit_batch_experiment.sh
bash -n gcp/submit_batch_experiment.sh
```

`bash -n` should return silently. If it prints an error, fix the script before
submitting a Batch job.

The helper accepts:

```bash
./gcp/submit_batch_experiment.sh \
  JOB_NAME \
  "PYTHON_EXPERIMENT_COMMAND" \
  MACHINE_TYPE \
  MAX_RUN_SECONDS \
  CPU_MILLI \
  MEMORY_MIB
```

Useful starting points:

- `n2-standard-4`: `CPU_MILLI=4000`, `MEMORY_MIB=16000`
- `n2-standard-8`: `CPU_MILLI=8000`, `MEMORY_MIB=32000`
- `n2-standard-16`: `CPU_MILLI=16000`, `MEMORY_MIB=64000`

The default boot disk is 100 GiB. Override it if needed:

```bash
export BOOT_DISK_GB=200
```

---

## 7. Run a smoke test

Submit a tiny end-to-end run first:

```bash
./gcp/submit_batch_experiment.sh \
  "kuhn-h2h-smoke-$(date +%Y%m%d-%H%M%S)" \
  "python -m kuhn_head_to_head.run all --smoke --output-root outputs/cloud/smoke" \
  "n2-standard-4" \
  "3600" \
  "4000" \
  "16000"
```

List jobs:

```bash
gcloud batch jobs list --location "$REGION"
```

View the job:

```bash
export JOB_NAME="kuhn-h2h-smoke-YYYYMMDD-HHMMSS"
gcloud batch jobs describe "$JOB_NAME" --location "$REGION"
```

After completion, check Cloud Storage:

```bash
gcloud storage ls "${BUCKET}/${JOB_NAME}/outputs/"
```

The smoke output should contain the same files produced locally, including:

- `entrant_training_summary.csv`
- `head_to_head_exact_pairwise.csv`
- `head_to_head_exact_mean_matrix.csv`
- `algorithm_ranking.csv`
- `plots/head_to_head_exact_mean_matrix.png`

---

## 8. Run the thesis head-to-head experiment

Run the default selected entrants on the common five-seed set:

```bash
./gcp/submit_batch_experiment.sh \
  "kuhn-h2h-thesis-5seed-$(date +%Y%m%d-%H%M%S)" \
  "python -m kuhn_head_to_head.run all \
    --seeds 1234,2025,31415,27182,16180 \
    --output-root outputs/cloud/thesis-5seed" \
  "n2-standard-8" \
  "43200" \
  "8000" \
  "32000"
```

For a ten-seed run:

```bash
./gcp/submit_batch_experiment.sh \
  "kuhn-h2h-thesis-10seed-$(date +%Y%m%d-%H%M%S)" \
  "python -m kuhn_head_to_head.run all \
    --seeds 1234,2025,31415,27182,16180,4242,8675309,7,99,1001 \
    --output-root outputs/cloud/thesis-10seed" \
  "n2-standard-16" \
  "86400" \
  "16000" \
  "64000"
```

If you receive final configuration overrides, commit a JSON file such as
`configs/thesis_head_to_head.json`, then pass it to the runner:

```bash
./gcp/submit_batch_experiment.sh \
  "kuhn-h2h-configured-$(date +%Y%m%d-%H%M%S)" \
  "python -m kuhn_head_to_head.run all \
    --config configs/thesis_head_to_head.json \
    --output-root outputs/cloud/configured" \
  "n2-standard-8" \
  "43200" \
  "8000" \
  "32000"
```

---

## 9. Monitor logs

List recent jobs:

```bash
gcloud batch jobs list --location "$REGION"
```

Describe a job:

```bash
gcloud batch jobs describe "$JOB_NAME" --location "$REGION"
```

Read Cloud Logging entries for a job:

```bash
gcloud logging read \
  "resource.type=batch_task AND labels.job_uid:*" \
  --project "$PROJECT_ID" \
  --limit 100 \
  --format="value(textPayload)"
```

The uploaded `batch_run.log` in Cloud Storage is usually the easiest artifact to
inspect:

```bash
gcloud storage cp "${BUCKET}/${JOB_NAME}/outputs/batch_run.log" .
sed -n '1,240p' batch_run.log
```

---

## 10. Retrieve outputs locally

Copy the complete output tree:

```bash
mkdir -p cloud_outputs
gcloud storage cp -r "${BUCKET}/${JOB_NAME}/outputs" "cloud_outputs/${JOB_NAME}"
```

The most important thesis artifacts are:

- `head_to_head_exact_mean_matrix.csv`
- `head_to_head_seed_win_fraction_matrix.csv`
- `head_to_head_aggregate_strength_summary.csv`
- `algorithm_ranking.csv`
- `plots/head_to_head_exact_mean_matrix.png`
- `plots/head_to_head_seed_win_fraction_matrix.png`
- `plots/head_to_head_aggregate_strength.png`

---

## 11. Re-run analysis only

If training succeeds but you want to regenerate plots or CSVs, run analysis
against an existing output directory. First retrieve or keep the original run
directory, then run:

```bash
python -m kuhn_head_to_head.run analyse \
  --run-dir outputs/cloud/thesis-5seed/kuhn_poker_algorithm_head_to_head_YYYYMMDD_HHMMSS
```

The runner reuses `experiment_metadata.json` from the run directory when no
new `--config` is supplied.

---

## 12. Troubleshooting

If the job fails quickly with exit code `128`, inspect the Batch job description
or Cloud Logging for the first `git clone` command. The failed smoke job
`kuhn-h2h-smoke-20260613-232144` failed this way because `SOURCE_REPO_URL` was
still set to the placeholder `https://github.com/your-org/kuhn-poker-head-to-head.git`.
The helper now defaults to the real head-to-head repo URL and rejects obvious
placeholder URLs before submitting a job.

If the job fails during virtual environment creation with a message like
`Unable to symlink ''`, this is a Debian Batch image `venv` issue. The helper
now follows the working Kuhn DREAM pattern: install `python3.9-venv` and create
the environment with `python3.9 -m venv --copies` under `/tmp`.

If cleanup upload fails with a Google Cloud SDK or `gsutil` Python error, use
the current helper. It uploads through `scripts/upload_outputs_to_gcs.py` from
the experiment virtual environment, matching the robust Deep CFR upload path.

If the job fails with `ModuleNotFoundError` for `deep_cfr_poker`,
`dream_poker`, or `escher_poker`, the Batch VM did not clone the sibling repos
in the expected layout. Check `SOURCE_REPO_URL`, `DEEP_CFR_REPO_URL`,
`DREAM_REPO_URL`, `ESCHER_REPO_URL`, the branch refs, and the directory tree in
`batch_run.log`.

If dependency installation fails, first rerun the smoke job. For private repos,
confirm that the VM can authenticate to Git before installing Python packages.

If the job runs out of memory, increase the machine type and memory request,
for example `n2-standard-16`, `CPU_MILLI=16000`, `MEMORY_MIB=64000`.

If the job times out, increase `MAX_RUN_SECONDS`. The ESCHER entrant is usually
the slowest component of the combined run.

If outputs are missing from Cloud Storage, inspect `batch_status.json` and
`batch_run.log`. The helper uploads `outputs/` after the experiment command
returns, even when the command exits non-zero.
