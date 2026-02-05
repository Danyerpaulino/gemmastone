import asyncio
import base64
import io
import json
from typing import Any, Literal

import httpx
import numpy as np

from app.core.settings import get_settings


class MedGemmaClient:
    def __init__(
        self,
        mode: Literal["local", "http", "vertex", "mock"] | None = None,
        http_url: str | None = None,
        analyze_url: str | None = None,
        generate_url: str | None = None,
        model_path: str | None = None,
        vertex_endpoint: str | None = None,
        vertex_project: str | None = None,
        vertex_location: str | None = None,
    ):
        settings = get_settings()
        self.mode = mode or settings.medgemma_mode
        self.http_url = http_url or settings.medgemma_http_url or settings.medgemma_endpoint
        self.analyze_url = analyze_url or settings.medgemma_analyze_url
        self.generate_url = generate_url or settings.medgemma_generate_url
        self.model_path = model_path or settings.medgemma_model_path
        self.vertex_endpoint = vertex_endpoint or settings.medgemma_vertex_endpoint
        self.vertex_project = vertex_project or settings.medgemma_vertex_project
        self.vertex_location = vertex_location or settings.medgemma_vertex_location

        self._local_processor = None
        self._local_model = None

    async def analyze_ct(self, volume: np.ndarray, prompt: str, modality: str = "CT") -> dict:
        key_slices = self._extract_key_slices(volume, num_slices=8)
        png_slices = [self._to_png_bytes(sl) for sl in key_slices]

        if self.mode == "local":
            return await self._local_analyze(prompt, png_slices, modality=modality)
        if self.mode == "vertex":
            return await self._vertex_analyze(prompt, png_slices, modality=modality)
        if self.mode == "http":
            return await self._http_analyze(prompt, png_slices, modality=modality)
        if self.mode == "mock":
            return self._mock_analysis()

        raise ValueError(f"Unsupported MedGemma mode: {self.mode}")

    async def generate_text(self, prompt: str) -> str:
        if self.mode == "local":
            return await self._local_generate(prompt)
        if self.mode == "vertex":
            return await self._vertex_generate(prompt)
        if self.mode == "http":
            return await self._http_generate(prompt)
        if self.mode == "mock":
            return "This is a mock summary. Stay hydrated and follow your plan."

        raise ValueError(f"Unsupported MedGemma mode: {self.mode}")

    async def _http_analyze(self, prompt: str, png_slices: list[bytes], modality: str) -> dict:
        if not self.http_url and not self.analyze_url:
            raise ValueError("MEDGEMMA_HTTP_URL or MEDGEMMA_ANALYZE_URL must be set for http mode")
        url = self.analyze_url or (self.http_url.rstrip("/") + "/analyze")
        payload = {
            "prompt": prompt,
            "modality": modality,
            "images": [base64.b64encode(png).decode("ascii") for png in png_slices],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return self._normalize_analysis_output(data)

    async def _http_generate(self, prompt: str) -> str:
        if not self.http_url and not self.generate_url:
            raise ValueError("MEDGEMMA_HTTP_URL or MEDGEMMA_GENERATE_URL must be set for http mode")
        url = self.generate_url or (self.http_url.rstrip("/") + "/generate")
        payload = {"prompt": prompt}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, dict) and "text" in data:
            return data["text"]
        if isinstance(data, str):
            return data
        return json.dumps(data)

    async def _vertex_analyze(self, prompt: str, png_slices: list[bytes], modality: str) -> dict:
        images = [base64.b64encode(png).decode("ascii") for png in png_slices]
        output = await self._vertex_predict({"prompt": prompt, "modality": modality, "images": images})
        return self._normalize_analysis_output(output)

    async def _vertex_generate(self, prompt: str) -> str:
        output = await self._vertex_predict({"prompt": prompt})
        if isinstance(output, dict) and "text" in output:
            return output["text"]
        if isinstance(output, str):
            return output
        return json.dumps(output)

    async def _vertex_predict(self, instance: dict[str, Any]) -> Any:
        try:
            from google.cloud import aiplatform
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-aiplatform is required for MEDGEMMA_MODE=vertex"
            ) from exc

        if not self.vertex_endpoint:
            raise ValueError("MEDGEMMA_VERTEX_ENDPOINT must be set for vertex mode")

        def _predict():
            if self.vertex_project and self.vertex_location:
                aiplatform.init(project=self.vertex_project, location=self.vertex_location)
            endpoint = aiplatform.Endpoint(self.vertex_endpoint)
            response = endpoint.predict(instances=[instance])
            if response.predictions:
                return response.predictions[0]
            return {}

        return await asyncio.to_thread(_predict)

    async def _local_analyze(self, prompt: str, png_slices: list[bytes], modality: str) -> dict:
        output = await self._local_generate_with_images(prompt, png_slices, modality=modality)
        return self._normalize_analysis_output(output)

    async def _local_generate(self, prompt: str) -> str:
        output = await self._local_generate_with_images(prompt, [])
        if isinstance(output, str):
            return output
        if isinstance(output, dict) and "text" in output:
            return output["text"]
        return json.dumps(output)

    async def _local_generate_with_images(
        self, prompt: str, png_slices: list[bytes], modality: str | None = None
    ) -> Any:
        self._ensure_local_model()

        from PIL import Image

        images = []
        for png in png_slices:
            images.append(Image.open(io.BytesIO(png)))

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({"type": "image", "image": img})

        messages = [{"role": "user", "content": content}]
        processor = self._local_processor
        model = self._local_model

        def _run():
            inputs = processor.apply_chat_template(messages, return_tensors="pt").to(model.device)
            outputs = model.generate(**inputs, max_new_tokens=512, do_sample=False)
            return processor.decode(outputs[0], skip_special_tokens=True)

        return await asyncio.to_thread(_run)

    def _ensure_local_model(self) -> None:
        if self._local_model is not None:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "transformers and torch are required for MEDGEMMA_MODE=local"
            ) from exc

        model_id = self.model_path or "google/medgemma-1.5-4b-it"
        self._local_processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self._local_model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )

    def _extract_key_slices(self, volume: np.ndarray, num_slices: int) -> list[np.ndarray]:
        if volume.ndim != 3:
            raise ValueError("CT volume must be 3D")
        total_slices = volume.shape[0]
        indices = np.linspace(0, total_slices - 1, num_slices, dtype=int)
        return [volume[i] for i in indices]

    def _to_png_bytes(self, array: np.ndarray) -> bytes:
        from PIL import Image

        arr = array.astype(np.float32)
        if arr.max() == arr.min():
            normalized = np.zeros_like(arr, dtype=np.uint8)
        else:
            normalized = ((arr - arr.min()) / (arr.max() - arr.min()) * 255).astype(np.uint8)
        img = Image.fromarray(normalized)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _normalize_analysis_output(self, output: Any) -> dict:
        if isinstance(output, dict):
            return output
        if isinstance(output, list) and output and isinstance(output[0], dict):
            return output[0]
        if isinstance(output, str):
            text = output.strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        return json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        pass
        raise ValueError("Unable to parse MedGemma analysis output")

    def _mock_analysis(self) -> dict:
        return {
            "stones": [
                {
                    "location": "kidney_lower",
                    "size_mm": 6.2,
                    "hounsfield_units": 950,
                    "shape": "round",
                    "hydronephrosis": "none",
                }
            ],
            "confidence": 0.45,
        }
