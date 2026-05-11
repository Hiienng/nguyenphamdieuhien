"""
ImageKit upload/delete via REST API.

Auth: HTTP Basic with private_key as username, empty password.
Docs: https://imagekit.io/docs/api-reference/upload-file/upload-file
"""
import base64
import logging
from typing import Iterable

import httpx

from ..core.config import get_settings

logger = logging.getLogger(__name__)

UPLOAD_URL = "https://upload.imagekit.io/api/v1/files/upload"
FILES_API = "https://api.imagekit.io/v1/files"

# Singleton HTTP client for connection pooling (reused across all uploads)
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=180, limits=httpx.Limits(max_connections=32, max_keepalive_connections=16))
    return _client


def _auth_header() -> dict[str, str]:
    settings = get_settings()
    if not settings.IMAGEKIT_PRIVATE_KEY:
        raise RuntimeError("IMAGEKIT_PRIVATE_KEY is not configured")
    token = base64.b64encode(f"{settings.IMAGEKIT_PRIVATE_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def upload_image(
    filename: str, content: bytes, batch_id: str
) -> dict:
    """Upload one image to ImageKit. Returns {name, url, fileId}."""
    settings = get_settings()
    folder = f"{settings.IMAGEKIT_FOLDER.rstrip('/')}/{batch_id}"

    files = {
        "file": (filename, content),
        "fileName": (None, filename),
        "folder": (None, folder),
        "useUniqueFileName": (None, "true"),
        "tags": (None, f"EtseeMate,batch-{batch_id}"),
    }
    client = await _get_client()
    resp = await client.post(UPLOAD_URL, headers=_auth_header(), files=files)
    if resp.status_code != 200:
        raise RuntimeError(f"ImageKit upload failed {resp.status_code}: {resp.text}")
    data = resp.json()
    return {"name": data["name"], "url": data["url"], "fileId": data["fileId"]}


async def fetch_image_bytes(url: str) -> bytes:
    """Download image bytes from a public ImageKit URL."""
    client = await _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content


async def delete_files(file_ids: Iterable[str]) -> None:
    """Bulk delete by fileId. Silently logs failures (cleanup must not block flow)."""
    ids = [fid for fid in file_ids if fid]
    if not ids:
        return
    try:
        client = await _get_client()
        resp = await client.post(
            f"{FILES_API}/batch/deleteByFileIds",
            headers={**_auth_header(), "Content-Type": "application/json"},
            json={"fileIds": ids},
        )
        if resp.status_code not in (200, 204):
            logger.warning(
                "ImageKit batch delete returned %d: %s", resp.status_code, resp.text
            )
    except Exception as e:
        logger.warning("ImageKit delete failed: %s", e)
