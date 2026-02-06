#!/bin/bash
# Quick update script for MedGemma on Vertex AI
# Usage: ./update-vertex.sh

set -e

PROJECT_ID="gen-lang-client-0599521132"
REGION="us-central1"
ENDPOINT_ID="5347143848688615424"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/medgemma-repo/medgemma-service:latest"

echo "=== MedGemma Vertex AI Update ==="
echo "This will take ~20-25 minutes total"
echo ""

# Check HF_TOKEN
if [ -z "${HF_TOKEN}" ]; then
    echo "ERROR: HF_TOKEN not set. Run: export HF_TOKEN=hf_xxx"
    exit 1
fi

# Step 1: Build
echo "[1/4] Building container (~15 mins)..."
gcloud builds submit --project=${PROJECT_ID} --region=${REGION} --tag=${IMAGE} .

# Step 2: Get current deployed model ID
echo "[2/4] Getting current deployment..."
CURRENT_DEPLOYED=$(gcloud ai endpoints describe ${ENDPOINT_ID} --project=${PROJECT_ID} --region=${REGION} --format="value(deployedModels[0].id)" 2>/dev/null || echo "")

# Step 3: Upload new model
echo "[3/4] Uploading new model version..."
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
gcloud ai models upload \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --display-name="medgemma-${TIMESTAMP}" \
    --container-image-uri="${IMAGE}" \
    --container-ports=8080 \
    --container-predict-route="/predict" \
    --container-health-route="/health" \
    --container-env-vars="MEDGEMMA_MODEL_ID=google/medgemma-1.5-4b-it,HF_TOKEN=${HF_TOKEN}"

# Get new model ID
NEW_MODEL=$(gcloud ai models list --project=${PROJECT_ID} --region=${REGION} --filter="displayName=medgemma-${TIMESTAMP}" --format="value(name)" | head -1)
echo "New model ID: ${NEW_MODEL}"

# Step 4: Swap deployment
echo "[4/4] Deploying to endpoint (~10 mins)..."

# Undeploy old if exists
if [ -n "${CURRENT_DEPLOYED}" ]; then
    echo "Undeploying old model: ${CURRENT_DEPLOYED}"
    gcloud ai endpoints undeploy-model ${ENDPOINT_ID} \
        --project=${PROJECT_ID} \
        --region=${REGION} \
        --deployed-model-id=${CURRENT_DEPLOYED} || true
fi

# Deploy new
gcloud ai endpoints deploy-model ${ENDPOINT_ID} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --model=${NEW_MODEL} \
    --display-name="medgemma-deployed" \
    --machine-type="g2-standard-8" \
    --accelerator="type=nvidia-l4,count=1" \
    --min-replica-count=1 \
    --max-replica-count=1

echo ""
echo "=== Update complete! ==="
echo "Test with: python scripts/seed_demo.py --api-url https://kidneystone-api-104069018874.us-central1.run.app/api --api-token YOUR_TOKEN"
