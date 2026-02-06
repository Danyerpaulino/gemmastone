#!/bin/bash
# Deploy MedGemma Multimodal Service to Vertex AI Custom Prediction
#
# This uses Vertex AI Endpoints instead of Cloud Run, which has different GPU quota.
#
# Usage:
#   ./deploy-vertex.sh [PROJECT_ID] [REGION]

set -e

PROJECT_ID="${1:-$(gcloud config get-value project)}"
REGION="${2:-us-central1}"
SERVICE_NAME="medgemma-service"
REPO_NAME="medgemma-repo"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"
MODEL_NAME="medgemma-multimodal"
ENDPOINT_NAME="medgemma-endpoint"

echo "=========================================="
echo "MedGemma Vertex AI Deployment"
echo "=========================================="
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "Image:    ${IMAGE_NAME}"
echo "Model:    ${MODEL_NAME}"
echo "Endpoint: ${ENDPOINT_NAME}"
echo "=========================================="

# Check if HF_TOKEN is set
if [ -z "${HF_TOKEN}" ]; then
    echo ""
    echo "ERROR: HF_TOKEN environment variable not set."
    echo "Export: export HF_TOKEN=hf_your_token_here"
    exit 1
fi

# Enable Vertex AI API
echo ""
echo "Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com --project="${PROJECT_ID}"

# Upload model to Vertex AI Model Registry
echo ""
echo "Uploading model to Vertex AI..."

# Check if model already exists
EXISTING_MODEL=$(gcloud ai models list \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --filter="displayName=${MODEL_NAME}" \
    --format="value(name)" 2>/dev/null | head -1)

if [ -n "${EXISTING_MODEL}" ]; then
    echo "Model ${MODEL_NAME} already exists: ${EXISTING_MODEL}"
    MODEL_ID="${EXISTING_MODEL}"
else
    echo "Creating new model..."
    gcloud ai models upload \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --display-name="${MODEL_NAME}" \
        --container-image-uri="${IMAGE_NAME}" \
        --container-ports=8080 \
        --container-predict-route="/analyze" \
        --container-health-route="/health" \
        --container-env-vars="MEDGEMMA_MODEL_ID=google/medgemma-1.5-4b-it,HF_TOKEN=${HF_TOKEN}"

    # Get the model ID
    MODEL_ID=$(gcloud ai models list \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --filter="displayName=${MODEL_NAME}" \
        --format="value(name)" | head -1)
fi

echo "Model ID: ${MODEL_ID}"

# Create endpoint if it doesn't exist
echo ""
echo "Setting up endpoint..."

EXISTING_ENDPOINT=$(gcloud ai endpoints list \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --filter="displayName=${ENDPOINT_NAME}" \
    --format="value(name)" 2>/dev/null | head -1)

if [ -n "${EXISTING_ENDPOINT}" ]; then
    echo "Endpoint ${ENDPOINT_NAME} already exists: ${EXISTING_ENDPOINT}"
    ENDPOINT_ID="${EXISTING_ENDPOINT}"
else
    echo "Creating new endpoint..."
    gcloud ai endpoints create \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --display-name="${ENDPOINT_NAME}"

    ENDPOINT_ID=$(gcloud ai endpoints list \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --filter="displayName=${ENDPOINT_NAME}" \
        --format="value(name)" | head -1)
fi

echo "Endpoint ID: ${ENDPOINT_ID}"

# Deploy model to endpoint with L4 GPU
echo ""
echo "Deploying model to endpoint with L4 GPU..."
echo "This may take 10-15 minutes..."

gcloud ai endpoints deploy-model "${ENDPOINT_ID}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --model="${MODEL_ID}" \
    --display-name="${MODEL_NAME}-deployed" \
    --machine-type="g2-standard-8" \
    --accelerator="type=nvidia-l4,count=1" \
    --min-replica-count=1 \
    --max-replica-count=1

echo ""
echo "=========================================="
echo "Deployment complete!"
echo ""
echo "Endpoint ID: ${ENDPOINT_ID}"
echo ""
echo "To get the endpoint URL for your backend:"
echo "  MEDGEMMA_MODE=vertex"
echo "  MEDGEMMA_VERTEX_ENDPOINT=${ENDPOINT_ID}"
echo "  MEDGEMMA_VERTEX_PROJECT=${PROJECT_ID}"
echo "  MEDGEMMA_VERTEX_LOCATION=${REGION}"
echo ""
echo "Note: Vertex AI endpoints use a different API format."
echo "You may need to update the backend client to use rawPredict."
echo "=========================================="
