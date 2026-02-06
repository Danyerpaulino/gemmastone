# MedGemma Multimodal Service

A dedicated microservice for **MedGemma 1.5 4B** multimodal inference, designed for deployment on **Cloud Run with GPU**.

## Why This Service?

The default Model Garden "one-click deploy" for MedGemma uses vLLM, which is **text-only**. This service uses the HuggingFace transformers library directly, enabling **full multimodal support** for CT scans, X-rays, and other medical images.

## Architecture

```
┌──────────────────┐         ┌─────────────────────────┐
│  Backend API     │  HTTP   │  MedGemma Service       │
│  (Cloud Run)     │ ──────► │  (Cloud Run + L4 GPU)   │
│                  │         │                         │
│  MEDGEMMA_MODE   │         │  - /analyze (images)    │
│  = http          │         │  - /generate (text)     │
└──────────────────┘         │  - /health              │
                             └─────────────────────────┘
```

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **GPU Quota**: Request L4 GPU quota for Cloud Run in your region
   - Go to: IAM & Admin → Quotas
   - Search for "NVIDIA L4 GPU"
   - Request increase for Cloud Run
3. **Hugging Face Account**:
   - Create account at https://huggingface.co
   - Accept MedGemma terms at https://huggingface.co/google/medgemma-1.5-4b-it
   - Generate a read token at https://huggingface.co/settings/tokens

## Deployment

### Option 1: Quick Deploy Script

```bash
# Set your Hugging Face token
export HF_TOKEN=hf_your_token_here

# Deploy (uses current gcloud project)
cd medgemma-service
./deploy.sh

# Or specify project and region
./deploy.sh my-project-id us-central1
```

### Option 2: Cloud Build

```bash
cd medgemma-service

# Submit build
gcloud builds submit --config=cloudbuild.yaml \
    --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
```

### Option 3: Manual Steps

```bash
# 1. Build image
gcloud builds submit --tag gcr.io/YOUR_PROJECT/medgemma-service

# 2. Deploy with GPU
gcloud run deploy medgemma-service \
    --image gcr.io/YOUR_PROJECT/medgemma-service \
    --region us-central1 \
    --gpu=1 \
    --gpu-type=nvidia-l4 \
    --memory=24Gi \
    --cpu=4 \
    --concurrency=1 \
    --timeout=300 \
    --max-instances=1 \
    --min-instances=0 \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --set-env-vars="MEDGEMMA_MODEL_ID=google/medgemma-1.5-4b-it,HF_TOKEN=hf_xxx"
```

## Configuration

After deployment, configure your backend to use this service:

```bash
# In your backend .env or Cloud Run environment
MEDGEMMA_MODE=http
MEDGEMMA_HTTP_URL=https://medgemma-service-xxxxx-uc.a.run.app
```

## API Endpoints

### POST /analyze

Analyze medical images (CT slices, X-rays, etc.).

**Request:**
```json
{
  "prompt": "Analyze this CT scan for kidney stones. Return JSON with stones array...",
  "images": ["base64_encoded_png_1", "base64_encoded_png_2"],
  "modality": "CT",
  "max_tokens": 2000
}
```

**Response:**
```json
{
  "result": {
    "stones": [
      {
        "location": "kidney_lower",
        "size_mm": 6.2,
        "hounsfield_units": 950
      }
    ],
    "confidence": 0.85
  },
  "inference_time_ms": 1234.5
}
```

### POST /generate

Generate text (patient education, summaries, etc.).

**Request:**
```json
{
  "prompt": "Create a patient-friendly explanation about calcium oxalate kidney stones...",
  "max_tokens": 1000
}
```

**Response:**
```json
{
  "text": "Kidney stones form when...",
  "inference_time_ms": 567.8
}
```

### GET /health

Check service health and GPU status.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "gpu_available": true,
  "gpu_name": "NVIDIA L4"
}
```

## Cost Considerations

- **Cloud Run with L4 GPU**: ~$0.70/hour when running
- **Min instances = 0**: Service scales to zero when not in use
- **Cold start**: ~60-90 seconds (model loading)

For the competition demo, consider:
- Set `min-instances=1` before your demo to avoid cold starts
- Scale back to `min-instances=0` after

## Local Development

```bash
# With GPU
docker build -t medgemma-service .
docker run --gpus all -p 8080:8080 \
    -e HF_TOKEN=hf_xxx \
    medgemma-service

# Test
curl http://localhost:8080/health
```

## Troubleshooting

### "GPU quota exceeded"
Request L4 GPU quota increase in Google Cloud Console.

### "Model loading failed"
1. Check HF_TOKEN is set correctly
2. Verify you accepted MedGemma terms on Hugging Face
3. Check Cloud Run logs: `gcloud run logs read medgemma-service`

### "Out of memory"
The L4 GPU has 24GB VRAM which should be sufficient for MedGemma 4B. If issues persist, try reducing `max_tokens` in requests.

### Slow responses
- First request after cold start is slow (~60-90s) due to model loading
- Subsequent requests should be 2-10 seconds depending on input size
- Consider setting `min-instances=1` for consistent performance
