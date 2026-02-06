from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import shutil
from typing import Literal
from uuid import uuid4

from fastapi import UploadFile

from app.core.settings import get_settings


@dataclass(frozen=True)
class StoredObject:
    uri: str
    bucket: str | None
    name: str
    filename: str


@dataclass(frozen=True)
class SignedUpload:
    upload_url: str
    gcs_uri: str
    headers: dict[str, str]
    expires_in: int


class ObjectStorage:
    """Streams uploads to GCS (preferred) with a local fallback for dev/edge."""

    def __init__(self, mode: Literal["auto", "gcs", "local"] | None = None):
        settings = get_settings()
        resolved = (mode or settings.storage_mode or "auto").lower()
        if resolved == "auto":
            resolved = "gcs" if settings.gcs_bucket else "local"
        self.mode = resolved
        self.gcs_bucket = settings.gcs_bucket
        self.gcs_prefix = (settings.gcs_prefix or "").strip("/")
        self.local_root = self._resolve_local_root(settings.local_storage_root)

    def upload(self, upload_file: UploadFile) -> StoredObject:
        filename = Path(upload_file.filename or "ct_scan").name
        object_name = self._object_name(filename)

        if self.mode == "gcs":
            if not self.gcs_bucket:
                raise ValueError("GCS_BUCKET must be set when storage_mode=gcs")
            return self._upload_gcs(upload_file, object_name, filename)

        return self._upload_local(upload_file, filename)

    def download_to_path(self, stored: StoredObject, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)

        if self.mode == "gcs":
            if not stored.bucket:
                raise ValueError("Missing bucket for GCS download")
            from google.cloud import storage  # imported lazily for local dev

            client = storage.Client()
            bucket = client.bucket(stored.bucket)
            blob = bucket.blob(stored.name)
            with destination.open("wb") as handle:
                blob.download_to_file(handle)
            return destination

        src_path = Path(stored.uri)
        if src_path.resolve() == destination.resolve():
            return destination
        with src_path.open("rb") as src, destination.open("wb") as dest:
            shutil.copyfileobj(src, dest)
        return destination

    def sign_upload(
        self,
        filename: str,
        content_type: str | None = None,
        expires_in: int | None = None,
    ) -> SignedUpload:
        if self.mode != "gcs":
            raise ValueError("Signed uploads require STORAGE_MODE=gcs and GCS_BUCKET.")
        if not self.gcs_bucket:
            raise ValueError("GCS_BUCKET must be set for signed uploads.")

        object_name = self._object_name(filename)
        upload_headers = {"Content-Type": content_type or "application/octet-stream"}
        ttl_seconds = expires_in or get_settings().gcs_signed_url_ttl_seconds

        from google.cloud import storage  # imported lazily for local dev

        client = storage.Client()
        bucket = client.bucket(self.gcs_bucket)
        blob = bucket.blob(object_name)

        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=ttl_seconds),
            method="PUT",
            content_type=upload_headers["Content-Type"],
        )
        gcs_uri = f"gs://{self.gcs_bucket}/{object_name}"
        return SignedUpload(
            upload_url=upload_url,
            gcs_uri=gcs_uri,
            headers=upload_headers,
            expires_in=ttl_seconds,
        )

    def from_gcs_uri(self, uri: str, filename: str | None = None) -> StoredObject:
        bucket, name = _parse_gcs_uri(uri)
        return StoredObject(
            uri=uri,
            bucket=bucket,
            name=name,
            filename=filename or Path(name).name,
        )

    def _upload_gcs(
        self, upload_file: UploadFile, object_name: str, filename: str
    ) -> StoredObject:
        from google.cloud import storage  # imported lazily for local dev

        client = storage.Client()
        bucket = client.bucket(self.gcs_bucket)
        blob = bucket.blob(object_name)
        upload_file.file.seek(0)
        blob.upload_from_file(
            upload_file.file,
            content_type=upload_file.content_type or "application/octet-stream",
            rewind=True,
        )
        uri = f"gs://{self.gcs_bucket}/{object_name}"
        return StoredObject(uri=uri, bucket=self.gcs_bucket, name=object_name, filename=filename)

    def _upload_local(self, upload_file: UploadFile, filename: str) -> StoredObject:
        target_dir = self.local_root / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        upload_file.file.seek(0)
        with target_path.open("wb") as handle:
            shutil.copyfileobj(upload_file.file, handle)
        return StoredObject(uri=str(target_path), bucket=None, name=str(target_path), filename=filename)

    def _object_name(self, filename: str) -> str:
        token = uuid4().hex
        if self.gcs_prefix:
            return f"{self.gcs_prefix}/{token}/{filename}"
        return f"{token}/{filename}"

    def _resolve_local_root(self, configured: str) -> Path:
        root = Path(configured)
        if root.is_absolute():
            return root
        return Path(__file__).resolve().parents[2] / root


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("Expected a gs:// URI for GCS storage.")
    trimmed = uri[len("gs://") :]
    parts = trimmed.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid GCS URI format.")
    return parts[0], parts[1]
