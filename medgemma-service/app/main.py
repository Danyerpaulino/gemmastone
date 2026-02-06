"""
MedGemma Multimodal Service

A GPU-accelerated microservice for medical image analysis using
Google's MedGemma 1.5 4B multimodal model.

Capabilities:
- CT scan analysis: Stone detection, measurement, composition prediction
- MRI analysis: Soft tissue characterization
- X-ray interpretation: Chest, bone, and other radiographs
- Text generation: Patient education materials

Deployment:
- Vertex AI with L4 GPU (current production setup)
- Cloud Run with GPU (alternative, requires quota)
- Local Docker with NVIDIA GPU (development)

API Endpoints:
- POST /analyze: Image analysis with structured JSON output
- POST /generate: Text generation for patient materials
- POST /predict: Vertex AI compatible prediction endpoint
- GET /health: Service health and GPU status

Model: google/medgemma-1.5-4b-it (instruction-tuned, multimodal)
"""

import base64
import io
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model references (loaded once at startup)
_model = None
_processor = None


class AnalyzeRequest(BaseModel):
    """Request for CT/MRI image analysis."""

    prompt: str = Field(..., description="Analysis prompt/instructions")
    images: list[str] = Field(
        default_factory=list,
        description="Base64-encoded PNG images (CT slices, X-rays, etc.)",
    )
    modality: str = Field(default="CT", description="Imaging modality (CT, MRI, XR, etc.)")
    max_tokens: int = Field(default=2000, ge=1, le=8192)


class AnalyzeResponse(BaseModel):
    """Response from image analysis."""

    result: dict[str, Any]
    inference_time_ms: float


class GenerateRequest(BaseModel):
    """Request for text generation."""

    prompt: str = Field(..., description="Text prompt")
    max_tokens: int = Field(default=1000, ge=1, le=8192)


class GenerateResponse(BaseModel):
    """Response from text generation."""

    text: str
    inference_time_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    gpu_available: bool
    gpu_name: str | None = None


def load_model():
    """Load MedGemma model and processor."""
    global _model, _processor

    if _model is not None:
        return

    model_id = os.getenv("MEDGEMMA_MODEL_ID", "google/medgemma-1.5-4b-it")
    logger.info(f"Loading MedGemma model: {model_id}")

    try:
        from transformers import AutoModelForImageTextToText, AutoProcessor

        # Check for GPU
        if torch.cuda.is_available():
            logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
            device_map = "auto"
            torch_dtype = torch.bfloat16
        else:
            logger.warning("No GPU available, using CPU (will be slow)")
            device_map = "cpu"
            torch_dtype = torch.float32

        _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        _model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
        )

        logger.info("MedGemma model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    load_model()
    yield


app = FastAPI(
    title="MedGemma Multimodal Service",
    description="Multimodal medical image analysis with MedGemma 1.5 4B",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and model status."""
    gpu_available = torch.cuda.is_available()
    return HealthResponse(
        status="healthy" if _model is not None else "loading",
        model_loaded=_model is not None,
        gpu_available=gpu_available,
        gpu_name=torch.cuda.get_device_name(0) if gpu_available else None,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_images(request: AnalyzeRequest):
    """
    Analyze medical images (CT slices, X-rays, etc.) using MedGemma.

    Expects base64-encoded PNG images. Returns structured JSON analysis.
    """
    return await _run_analysis(
        prompt=request.prompt,
        images=request.images,
        modality=request.modality,
        max_tokens=request.max_tokens,
    )


@app.post("/predict")
async def vertex_predict(request: dict[str, Any]):
    """
    Vertex AI prediction endpoint.

    Handles Vertex AI's {"instances": [...]} format and routes to analysis.
    """
    instances = request.get("instances", [])
    if not instances:
        raise HTTPException(status_code=400, detail="No instances provided")

    predictions = []
    for instance in instances:
        result = await _run_analysis(
            prompt=instance.get("prompt", "Analyze this medical image."),
            images=instance.get("images", []),
            modality=instance.get("modality", "CT"),
            max_tokens=instance.get("max_tokens", 2000),
        )
        predictions.append(result.dict())

    return {"predictions": predictions}


async def _run_analysis(
    prompt: str,
    images: list[str],
    modality: str = "CT",
    max_tokens: int = 2000,
) -> AnalyzeResponse:
    """Core analysis logic shared by /analyze and /predict endpoints."""
    if _model is None or _processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start_time = time.time()

    try:
        # Decode images
        pil_images = []
        for b64_img in images:
            img_bytes = base64.b64decode(b64_img)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            pil_images.append(img)

        # Build message content (images first, then text)
        content = []
        for img in pil_images:
            content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]

        # Run inference
        inputs = _processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(_model.device, dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)

        input_len = inputs["input_ids"].shape[-1]

        with torch.inference_mode():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
            )
            generation = outputs[0][input_len:]

        output_text = _processor.decode(generation, skip_special_tokens=True)

        # Try to parse as JSON
        result = _parse_json_output(output_text)

        inference_time = (time.time() - start_time) * 1000

        return AnalyzeResponse(result=result, inference_time_ms=inference_time)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """
    Generate text using MedGemma (for patient education, summaries, etc.).
    """
    if _model is None or _processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start_time = time.time()

    try:
        messages = [{"role": "user", "content": [{"type": "text", "text": request.prompt}]}]

        inputs = _processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(_model.device, dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)

        input_len = inputs["input_ids"].shape[-1]

        with torch.inference_mode():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                do_sample=False,
            )
            generation = outputs[0][input_len:]

        output_text = _processor.decode(generation, skip_special_tokens=True)

        inference_time = (time.time() - start_time) * 1000

        return GenerateResponse(text=output_text, inference_time_ms=inference_time)

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_json_output(text: str) -> dict:
    """Parse model output as JSON, handling common formatting issues."""
    text = text.strip()

    def _ensure_dict(parsed: Any) -> dict:
        """Ensure the result is a dict, wrapping lists if needed."""
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            # Model returned a list of stones directly - wrap it
            return {"stones": parsed, "confidence": 0.8}
        return {"raw_output": str(parsed)}

    # Try direct parse
    try:
        parsed = json.loads(text)
        return _ensure_dict(parsed)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                parsed = json.loads(text[start:end].strip())
                return _ensure_dict(parsed)
            except json.JSONDecodeError:
                pass

    # Try to find JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return _ensure_dict(parsed)
        except json.JSONDecodeError:
            pass

    # Try to find JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return _ensure_dict(parsed)
        except json.JSONDecodeError:
            pass

    # Return as wrapped text if JSON parsing fails
    return {"raw_output": text, "parse_error": "Could not parse as JSON"}
