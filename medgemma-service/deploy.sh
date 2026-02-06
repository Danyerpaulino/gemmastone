#!/bin/bash
# Deploy MedGemma Multimodal Service to Cloud Run with GPU
#
# Prerequisites:
# 1. gcloud CLI installed and authenticated
# 2. Cloud Run API enabled
# 3. GPU quota approved for your project
# 4. Hugging Face token set (for gated model access)
#
# Usage:
#   ./deploy.sh [PROJECT_ID] [REGION]

set -e

PROJECT_ID="${1:-$(gcloud config get-value project)}"
REGION="${2:-us-central1}"
SERVICE_NAME="medgemma-service"
REPO_NAME="medgemma-repo"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

echo "=========================================="
echo "MedGemma Multimodal Service Deployment"
echo "=========================================="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image:   ${IMAGE_NAME}"
echo "=========================================="

# Check if HF_TOKEN is set (needed for gated model)
if [ -z "${HF_TOKEN}" ]; then
    echo ""
    echo "WARNING: HF_TOKEN environment variable not set."
    echo "MedGemma is a gated model - you need a Hugging Face token."
    echo ""
    echo "To get a token:"
    echo "1. Go to https://huggingface.co/settings/tokens"
    echo "2. Create a token with 'read' access"
    echo "3. Accept the model terms at https://huggingface.co/google/medgemma-1.5-4b-it"
    echo "4. Export: export HF_TOKEN=hf_your_token_here"
    echo ""
    read -p "Continue without HF_TOKEN? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Enable required APIs
echo ""
echo "Enabling required APIs..."
gcloud services enable run.googleapis.com --project="${PROJECT_ID}"
gcloud services enable cloudbuild.googleapis.com --project="${PROJECT_ID}"
gcloud services enable artifactregistry.googleapis.com --project="${PROJECT_ID}"

# Create Artifact Registry repository if it doesn't exist
echo ""
echo "Setting up Artifact Registry repository..."
if ! gcloud artifacts repositories describe ${REPO_NAME} \
    --project="${PROJECT_ID}" \
    --location="${REGION}" &>/dev/null; then
    echo "Creating repository ${REPO_NAME}..."
    gcloud artifacts repositories create ${REPO_NAME} \
        --project="${PROJECT_ID}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="MedGemma service images"
else
    echo "Repository ${REPO_NAME} already exists."
fi

# Build the container
echo ""
echo "Building container image..."
gcloud builds submit \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --tag="${IMAGE_NAME}:latest" \
    .

# Deploy to Cloud Run with GPU
echo ""
echo "Deploying to Cloud Run with L4 GPU..."

# Build the deploy command
# Note: With GPU, Cloud Run requires specific CPU/memory combinations
# L4 GPU + 8 CPU allows up to 32Gi memory
DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --image=${IMAGE_NAME}:latest \
    --platform=managed \
    --gpu=1 \
    --gpu-type=nvidia-l4 \
    --memory=16Gi \
    --cpu=8 \
    --concurrency=1 \
    --timeout=300 \
    --max-instances=1 \
    --min-instances=0 \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --set-env-vars=MEDGEMMA_MODEL_ID=google/medgemma-1.5-4b-it"

# Add HF_TOKEN if set
if [ -n "${HF_TOKEN}" ]; then
    DEPLOY_CMD="${DEPLOY_CMD},HF_TOKEN=${HF_TOKEN}"
fi

eval "${DEPLOY_CMD}"

# Get the service URL
echo ""
echo "=========================================="
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format="value(status.url)")

echo "Deployment complete!"
echo ""
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "To configure your backend, set:"
echo "  MEDGEMMA_MODE=http"
echo "  MEDGEMMA_HTTP_URL=${SERVICE_URL}"
echo ""
echo "Test the service:"
echo "  curl ${SERVICE_URL}/health"
echo "=========================================="
