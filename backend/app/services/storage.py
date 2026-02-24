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

    def __init__(
        self,
        mode: Literal["auto", "gcs", "local"] | None = None,
        prefix_override: str | None = None,
    ):
        settings = get_settings()
        resolved = (mode or settings.storage_mode or "auto").lower()
        if resolved == "auto":
            resolved = "gcs" if settings.gcs_bucket else "local"
        self.mode = resolved
        self.gcs_bucket = settings.gcs_bucket
        self.gcs_prefix = (prefix_override or settings.gcs_prefix or "").strip("/")
        self.local_prefix = (prefix_override or "").strip("/")
        self.local_root = self._resolve_local_root(settings.local_storage_root)

    def upload(self, upload_file: UploadFile) -> StoredObject:
        filename = Path(upload_file.filename or "ct_scan").name
        object_name = self._object_name(filename)

        if self.mode == "gcs":
            if not self.gcs_bucket:
                raise ValueError("GCS_BUCKET must be set when storage_mode=gcs")
            return self._upload_gcs(upload_file, object_name, filename)

        return self._upload_local(upload_file, filename)

    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> StoredObject:
        object_name = self._object_name(filename)

        if self.mode == "gcs":
            if not self.gcs_bucket:
                raise ValueError("GCS_BUCKET must be set when storage_mode=gcs")
            from google.cloud import storage  # imported lazily for local dev

            client = storage.Client()
            bucket = client.bucket(self.gcs_bucket)
            blob = bucket.blob(object_name)
            blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
            uri = f"gs://{self.gcs_bucket}/{object_name}"
            return StoredObject(
                uri=uri,
                bucket=self.gcs_bucket,
                name=object_name,
                filename=filename,
            )

        return self._upload_local_bytes(data, filename)

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

        # Build signing kwargs - use IAM signing if credentials lack a private key
        # (e.g., compute engine credentials on Cloud Run)
        sign_kwargs: dict = {
            "version": "v4",
            "expiration": timedelta(seconds=ttl_seconds),
            "method": "PUT",
            "content_type": upload_headers["Content-Type"],
        }

        # Check if we need to use IAM-based signing
        credentials = client._credentials
        if not hasattr(credentials, "sign_bytes"):
            # Credentials can't sign locally, use IAM signBlob API
            # This requires the service account to have iam.serviceAccounts.signBlob permission
            service_account_email = _get_service_account_email(credentials)
            if service_account_email:
                sign_kwargs["service_account_email"] = service_account_email

        upload_url = blob.generate_signed_url(**sign_kwargs)
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
        target_dir = self.local_root
        if self.local_prefix:
            target_dir = target_dir / self.local_prefix
        target_dir = target_dir / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        upload_file.file.seek(0)
        with target_path.open("wb") as handle:
            shutil.copyfileobj(upload_file.file, handle)
        return StoredObject(uri=str(target_path), bucket=None, name=str(target_path), filename=filename)

    def _upload_local_bytes(self, data: bytes, filename: str) -> StoredObject:
        target_dir = self.local_root
        if self.local_prefix:
            target_dir = target_dir / self.local_prefix
        target_dir = target_dir / uuid4().hex
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        with target_path.open("wb") as handle:
            handle.write(data)
        return StoredObject(uri=str(target_path), bucket=None, name=str(target_path), filename=filename)

    def public_url(self, stored: StoredObject) -> str:
        if self.mode == "gcs":
            if not stored.bucket:
                raise ValueError("Missing bucket for GCS object.")
            return f"https://storage.googleapis.com/{stored.bucket}/{stored.name}"
        return stored.uri

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


def _get_service_account_email(credentials) -> str | None:
    """Extract service account email from credentials for IAM-based signing."""
    # Compute engine credentials have service_account_email attribute
    if hasattr(credentials, "service_account_email"):
        return credentials.service_account_email

    # Try to get from the signer email if available
    if hasattr(credentials, "signer_email"):
        return credentials.signer_email

    # For impersonated credentials
    if hasattr(credentials, "_target_principal"):
        return credentials._target_principal

    # Fallback: try to fetch from metadata server (Cloud Run)
    try:
        import requests

        response = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
            headers={"Metadata-Flavor": "Google"},
            timeout=2,
        )
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass

    return None
