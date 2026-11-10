"""Cloudflare R2 access via the S3-compatible API.

Reading the catalog and card images happens over public URLs (config.card_image),
so this module is only needed for *writing* - adding/editing characters through
the bot. The S3 client is synchronous; call these from a thread (run_db).
"""

import json
from datetime import datetime, timezone

import boto3

from config import (
    R2_ACCESS_KEY_ID,
    R2_BUCKET,
    R2_ENDPOINT,
    R2_PREFIX,
    R2_SECRET_ACCESS_KEY,
    R2_WRITE_ENABLED,
)

CATALOG_KEY = "characters.json"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache, max-age=0, must-revalidate"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _client


def _full_key(relative: str) -> str:
    relative = relative.lstrip("/")
    return f"{R2_PREFIX}/{relative}" if R2_PREFIX else relative


def _require_write() -> None:
    if not R2_WRITE_ENABLED:
        raise RuntimeError("R2 write is not configured (check R2_ACCESS_KEY_ID/SECRET/BUCKET/ENDPOINT)")


def put_bytes(relative: str, data: bytes, content_type: str, cache_control: str = IMMUTABLE_CACHE) -> None:
    _require_write()
    _get_client().put_object(
        Bucket=R2_BUCKET,
        Key=_full_key(relative),
        Body=data,
        ContentType=content_type,
        CacheControl=cache_control,
    )


def get_bytes(relative: str) -> bytes:
    response = _get_client().get_object(Bucket=R2_BUCKET, Key=_full_key(relative))
    return response["Body"].read()


def delete_object(relative: str) -> None:
    _require_write()
    _get_client().delete_object(Bucket=R2_BUCKET, Key=_full_key(relative))


def list_filenames() -> list[str]:
    """Basenames of every object in the bucket.

    Used when picking a name for a new/edited card art: the catalog alone is not
    enough, because replacing art orphans the previous file, and a name that is
    free in the catalog may still exist in the bucket.
    """
    client = _get_client()
    base = f"{R2_PREFIX}/" if R2_PREFIX else ""
    names: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=base):
        for obj in page.get("Contents", ()):
            names.append(obj["Key"].rsplit("/", 1)[-1])
    return names


def load_catalog() -> dict:
    return json.loads(get_bytes(CATALOG_KEY))


def save_catalog(data: dict, backup: bool = True) -> None:
    """Write the catalog, keeping a timestamped copy of the previous version.

    Backups land under ``_history/characters.<UTC-timestamp>.json`` so a bad
    edit can be rolled back.
    """
    if backup:
        try:
            previous = get_bytes(CATALOG_KEY)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            put_bytes(f"_history/characters.{stamp}.json", previous, "application/json", cache_control=NO_CACHE)
        except Exception:  # noqa: BLE001
            pass  # first write / catalog missing - nothing to back up

    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    put_bytes(CATALOG_KEY, payload, "application/json", cache_control=NO_CACHE)
