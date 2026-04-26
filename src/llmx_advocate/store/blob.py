"""MinIO blob storage for large phase outputs (raw text, video JSON, etc.).

Threshold rule: if a serialised output exceeds INLINE_LIMIT bytes, persist to MinIO and
keep only the object key in the DB row. Below the limit → store inline JSON.
"""

from __future__ import annotations

import json
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from llmx_advocate.settings import get_settings

INLINE_LIMIT = 16 * 1024  # 16 KB


_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_bucket(bucket: str | None = None) -> str:
    settings = get_settings()
    name = bucket or settings.minio_bucket
    client = get_client()
    if not client.bucket_exists(name):
        client.make_bucket(name)
    return name


def put_json(key: str, data: dict) -> str:
    bucket = ensure_bucket()
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    client = get_client()
    client.put_object(bucket, key, BytesIO(payload), length=len(payload), content_type="application/json")
    return key


def get_json(key: str) -> dict:
    settings = get_settings()
    client = get_client()
    try:
        resp = client.get_object(settings.minio_bucket, key)
        return json.loads(resp.read().decode("utf-8"))
    finally:
        try:
            resp.close()
            resp.release_conn()
        except (UnboundLocalError, S3Error):
            pass


def put_or_inline(key_hint: str, data: dict) -> tuple[str | None, dict | None]:
    """Returns (blob_key, inline_payload) — exactly one is non-None."""
    serialised = json.dumps(data, ensure_ascii=False)
    if len(serialised.encode("utf-8")) > INLINE_LIMIT:
        return put_json(key_hint, data), None
    return None, data
