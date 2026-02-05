from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.core.settings import get_settings


class MessagingService:
    def __init__(self, mode: Literal["mock", "real"] | None = None):
        settings = get_settings()
        self.mode = mode or settings.messaging_mode
        self.api_key = settings.messaging_api_key
        self.phone_number = settings.messaging_phone_number
        self.messaging_profile_id = settings.messaging_profile_id
        self.voice_connection_id = settings.messaging_voice_connection_id
        self.webhook_base_url = settings.messaging_webhook_base_url

    def send_sms(self, to: str, message: str) -> str:
        if self.mode == "mock":
            return f"mock-sms-{int(datetime.utcnow().timestamp())}"
        return self._real_send_sms(to, message)

    def initiate_voice_call(self, to: str, client_state: str | None = None) -> str:
        if self.mode == "mock":
            return f"mock-call-{int(datetime.utcnow().timestamp())}"
        return self._real_voice_call(to, client_state)

    def generate_voice_response_xml(self, patient_name: str, fluid_goal_ml: int) -> str:
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            f"  <Speak>Hi {patient_name}. This is your kidney stone care assistant."
            f" Your daily water goal is {fluid_goal_ml} milliliters."
            " Did you meet your water goal today? Press 1 for yes, 2 for no.</Speak>\n"
            "  <Gather numDigits=\"1\" timeout=\"10\"/>\n"
            "  <Speak>I did not catch that. Goodbye.</Speak>\n"
            "  <Hangup/>\n"
            "</Response>"
        )

    def _real_send_sms(self, to: str, message: str) -> str:
        raise RuntimeError(
            "Real messaging providers are intentionally not wired in the public demo."
        )

    def _real_voice_call(self, to: str, client_state: str | None = None) -> str:
        raise RuntimeError(
            "Real messaging providers are intentionally not wired in the public demo."
        )
