"""App downloads for beta testers: the latest Android APK and the iPhone TestFlight link.

The Android workflow uploads each new APK with the admin token (PUT /admin/apk); anyone with the
link can download it from /download/android. Signing in still needs an allowlisted number and code.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.deps import require_admin

router = APIRouter(include_in_schema=False)

MAX_APK_BYTES = 150 * 1024 * 1024


def _paths() -> tuple[Path, Path]:
    folder = Path(get_settings().downloads_dir)
    return folder / "pickup.apk", folder / "pickup.json"


def apk_info() -> dict | None:
    apk, meta = _paths()
    if not apk.exists() or not meta.exists():
        return None
    try:
        return json.loads(meta.read_text())
    except ValueError:
        return None


@router.put("/admin/apk", dependencies=[Depends(require_admin)])
async def upload_apk(request: Request, version: str = Query(..., max_length=40)) -> dict:
    apk, meta = _paths()
    apk.parent.mkdir(parents=True, exist_ok=True)
    partial = apk.with_suffix(".part")
    digest = hashlib.sha256()
    size = 0
    with partial.open("wb") as out:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_APK_BYTES:
                out.close()
                partial.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "APK too large")
            digest.update(chunk)
            out.write(chunk)
    if size < 1024:
        partial.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That isn't an APK")
    os.replace(partial, apk)  # atomic: a download never sees half a file
    info = {"version": version, "size": size, "sha256": digest.hexdigest(), "uploaded_at": datetime.now(UTC).isoformat()}
    meta.write_text(json.dumps(info))
    return info


@router.get("/download/android")
async def download_apk() -> FileResponse:
    apk, _ = _paths()
    info = apk_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The Android app isn't published yet")
    return FileResponse(apk, media_type="application/vnd.android.package-archive", filename=f"Pickup-{info['version']}.apk")
