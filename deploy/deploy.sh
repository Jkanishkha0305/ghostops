#!/bin/bash
# GhostOps Cloud Run deployment
# Run from ghostops/ root: bash deploy/deploy.sh
# Earns bonus points for automated deployment (IaC rule in Gemini hackathon)

set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-ghostops-demo}"
REGION="us-central1"
SERVICE_NAME="ghostops-backend"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "==> Building Docker image..."
docker build -t "${IMAGE}" .

echo "==> Pushing to Container Registry..."
docker push "${IMAGE}"

echo "==> Deploying to Cloud Run (min-instances=1 prevents cold starts)..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --min-instances 1 \
  --max-instances 3 \
  --memory 512Mi \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --project "${PROJECT_ID}"

echo ""
echo "==> Deployment complete!"
echo "==> Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)"

echo ""
echo "==> Update CLOUD_RUN_URL in your .env with the URL above"
