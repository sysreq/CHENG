#!/usr/bin/env bash
# deploy.sh — Deploy CHENG to Google Cloud Run
#
# Usage:
#   ./deploy.sh [options]
#
# Options:
#   -p, --project   GCP project ID (required if not set via gcloud config)
#   -r, --region    GCP region (default: us-central1)
#   -s, --service   Cloud Run service name (default: cheng)
#   -t, --tag       Image tag (default: latest)
#   --skip-build    Skip docker build+push; deploy the existing image
#   --min-instances Minimum running instances (default: 1)
#   --help          Show this help message
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Docker installed and configured for Artifact Registry
#     (gcloud auth configure-docker ${REGION}-docker.pkg.dev)
#   - Artifact Registry repository created (see cloudbuild.yaml for setup steps)
#
# Example:
#   ./deploy.sh --project my-gcp-project --region us-central1

set -euo pipefail

# Defaults
REGION="us-central1"
SERVICE="cheng"
REPOSITORY="cheng-images"
TAG="latest"
SKIP_BUILD=false
MIN_INSTANCES=1

# Argument parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)    PROJECT_ID="$2"; shift 2 ;;
    -r|--region)     REGION="$2";     shift 2 ;;
    -s|--service)    SERVICE="$2";    shift 2 ;;
    -t|--tag)        TAG="$2";        shift 2 ;;
    --skip-build)    SKIP_BUILD=true; shift   ;;
    --min-instances) MIN_INSTANCES="$2"; shift 2 ;;
    --help)
      grep "^#" "$0" | head -25 | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Resolve project from gcloud config if not supplied
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [[ -z "${PROJECT_ID:-}" ]]; then
  echo "ERROR: GCP project ID required. Pass --project or run: gcloud config set project PROJECT_ID" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE}:${TAG}"

echo "============================================"
echo "  CHENG Cloud Run Deployment"
echo "============================================"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Service : ${SERVICE}"
echo "  Image   : ${IMAGE}"
echo "  Min inst: ${MIN_INSTANCES}"
echo "============================================"

# Build + push (unless --skip-build)
if [[ "${SKIP_BUILD}" == "false" ]]; then
  echo ""
  echo "[1/3] Building Docker image..."
  docker build --target runtime --tag "${IMAGE}" .

  echo ""
  echo "[2/3] Pushing image to Artifact Registry..."
  docker push "${IMAGE}"
else
  echo ""
  echo "[1/3] Skipping build (--skip-build)"
  echo "[2/3] Skipping push (--skip-build)"
fi

# Deploy to Cloud Run
echo ""
echo "[3/3] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --memory 2Gi \
  --cpu 2 \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances 10 \
  --concurrency 4 \
  --timeout 3600 \
  --set-env-vars CHENG_MODE=cloud \
  --allow-unauthenticated \
  --port 8080

echo ""
echo "Done! Service URL:"
gcloud run services describe "${SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)"
