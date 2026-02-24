from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import httpx

from app.core.settings import get_settings


@dataclass(frozen=True)
class TelnyxMessageResult:
    message_id: str
    status: str | None = None


class TelnyxClient:
    def __init__(
        self,
        api_key: str | None = None,
        messaging_profile_id: str | None = None,
        from_number: str | None = None,
        base_url: str | None = None,
        mode: Literal["mock", "live"] | None = None,
    ) -> None:
        settings = get_settings()
        self.mode = mode or settings.messaging_mode
        self.api_key = api_key or settings.telnyx_api_key or settings.messaging_api_key
        self.messaging_profile_id = (
            messaging_profile_id
            or settings.telnyx_messaging_profile_id
            or settings.messaging_profile_id
        )
        self.from_number = from_number or settings.telnyx_phone_number or settings.messaging_phone_number
        self.base_url = base_url or settings.telnyx_base_url

    def send_sms(self, to: str, text: str, media_urls: list[str] | None = None) -> TelnyxMessageResult:
        if self.mode == "mock" or not self.api_key:
            stamp = int(datetime.utcnow().timestamp())
            return TelnyxMessageResult(message_id=f"mock-sms-{stamp}", status="mock")

        payload: dict[str, object] = {"to": to, "text": text}
        if self.from_number:
            payload["from"] = self.from_number
        if self.messaging_profile_id:
            payload["messaging_profile_id"] = self.messaging_profile_id
        if media_urls:
            payload["media_urls"] = media_urls

        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json().get("data", {})
        message_id = data.get("id") or data.get("message_id") or ""
        status = data.get("status")
        return TelnyxMessageResult(message_id=message_id, status=status)
