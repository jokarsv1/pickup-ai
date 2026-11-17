"""App downloads for beta testers.

- Android: the latest release APK. The Android workflow uploads it (PUT /admin/apk).
- iPhone: an unsigned build (IPA) for sideloading with a free Apple ID (PUT /admin/ipa), until
  there's a TestFlight link. Sideloadly signs it on the tester's own computer.

Anyone with the link can download them. Signing in still needs an allowlisted number and code.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.deps import require_admin

router = APIRouter(include_in_schema=False)

MAX_BYTES = 150 * 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"  # APKs and IPAs are both zip files


@dataclass(frozen=True)
class Kind:
    file: str
    meta: str
    media_type: str
    suffix: str
    label: str


KINDS = {
    "android": Kind("pickup.apk", "pickup.json", "application/vnd.android.package-archive", "apk", "APK"),
    "ios": Kind("pickup-unsigned.ipa", "pickup-ios.json", "application/octet-stream", "ipa", "IPA"),
}


def _paths(kind: Kind) -> tuple[Path, Path]:
    folder = Path(get_settings().downloads_dir)
    return folder / kind.file, folder / kind.meta


def info(platform: str) -> dict | None:
    path, meta = _paths(KINDS[platform])
    if not path.exists() or not meta.exists():
        return None
    try:
        return json.loads(meta.read_text())
    except ValueError:
        return None


def apk_info() -> dict | None:
    return info("android")


async def _store(request: Request, kind: Kind, version: str) -> dict:
    path, meta = _paths(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    digest = hashlib.sha256()
    size = 0
    head = b""
    with partial.open("wb") as out:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                partial.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{kind.label} too large")
            if len(head) < 4:
                head += chunk[: 4 - len(head)]
            digest.update(chunk)
            out.write(chunk)
    if size < 1024 or head != ZIP_MAGIC:
        partial.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"That isn't an {kind.label}")
    os.replace(partial, path)  # atomic: a download never sees half a file
    result = {"version": version, "size": size, "sha256": digest.hexdigest(), "uploaded_at": datetime.now(UTC).isoformat()}
    meta.write_text(json.dumps(result))
    return result


def _serve(platform: str, missing: str) -> FileResponse:
    kind = KINDS[platform]
    current = info(platform)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, missing)
    path, _ = _paths(kind)
    return FileResponse(path, media_type=kind.media_type, filename=f"Pickup-{current['version']}.{kind.suffix}")


@router.put("/admin/apk", dependencies=[Depends(require_admin)])
async def upload_apk(request: Request, version: str = Query(..., max_length=40)) -> dict:
    return await _store(request, KINDS["android"], version)


@router.put("/admin/ipa", dependencies=[Depends(require_admin)])
async def upload_ipa(request: Request, version: str = Query(..., max_length=40)) -> dict:
    return await _store(request, KINDS["ios"], version)


@router.get("/download/android")
async def download_apk() -> FileResponse:
    return _serve("android", "The Android app isn't published yet")


@router.get("/download/ios")
async def download_ipa() -> FileResponse:
    return _serve("ios", "The iPhone preview isn't published yet")
