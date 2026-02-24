from __future__ import annotations

import base64
import io
import re
import secrets
import string

import qrcode

from app.core.settings import get_settings
from app.services.storage import ObjectStorage


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "provider"


def generate_referral_code(name: str, suffix_length: int = 4) -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(suffix_length))
    base_max = max(1, 20 - (suffix_length + 1))
    base = slugify(name)[:base_max]
    return f"{base}-{suffix}"


def build_join_url(referral_code: str) -> str:
    settings = get_settings()
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}/join/{referral_code}"


def generate_qr_code_url(referral_code: str) -> str:
    join_url = build_join_url(referral_code)
    image = qrcode.make(join_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()

    storage = ObjectStorage(prefix_override="qr-codes")
    if storage.mode == "gcs":
        stored = storage.upload_bytes(
            data,
            filename=f"qr-{referral_code}.png",
            content_type="image/png",
        )
        return storage.public_url(stored)

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"
