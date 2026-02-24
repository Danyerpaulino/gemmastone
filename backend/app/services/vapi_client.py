from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VapiCallResult:
    call_id: str
    status: str | None = None


class VapiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        call_path: str | None = None,
        assistant_id: str | None = None,
        phone_number_id: str | None = None,
        mode: Literal["mock", "live"] | None = None,
    ) -> None:
        settings = get_settings()
        self.mode = mode or settings.messaging_mode
        self.api_key = api_key or settings.vapi_api_key
        self.base_url = base_url or settings.vapi_base_url
        self.call_path = call_path or settings.vapi_call_path
        self.assistant_id = assistant_id or settings.vapi_assistant_id
        self.phone_number_id = phone_number_id or settings.vapi_phone_number_id

    def create_call(
        self,
        customer_number: str,
        patient_id: str | None = None,
        call_type: str | None = None,
        metadata: dict | None = None,
        system_prompt: str | None = None,
    ) -> VapiCallResult:
        if self.mode == "mock" or not self.api_key:
            stamp = int(datetime.utcnow().timestamp())
            return VapiCallResult(call_id=f"mock-call-{stamp}", status="mock")

        payload: dict[str, object] = {
            "assistantId": self.assistant_id,
            "phoneNumberId": self.phone_number_id,
            "customer": {"number": customer_number},
        }
        overrides: dict[str, object] = {}
        merged_metadata: dict[str, object] = {}
        if metadata:
            merged_metadata.update(metadata)
        if patient_id:
            merged_metadata.setdefault("patient_id", patient_id)
        if call_type:
            merged_metadata.setdefault("call_type", call_type)
        if merged_metadata:
            overrides["metadata"] = merged_metadata
        if system_prompt:
            overrides["model"] = {
                "provider": "openai",
                "model": "gpt-5.2-chat-latest",
                "messages": [{"role": "system", "content": system_prompt}],
            }
        if overrides:
            payload["assistantOverrides"] = overrides

        url = f"{self.base_url.rstrip('/')}/{self.call_path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if not resp.is_success:
                logger.error(
                    "Vapi call creation failed: %s %s — %s",
                    resp.status_code,
                    resp.reason_phrase,
                    resp.text,
                )
                resp.raise_for_status()
            data = resp.json()
        call_id = data.get("id") or data.get("callId") or data.get("call_id") or ""
        status = data.get("status")
        return VapiCallResult(call_id=call_id, status=status)
