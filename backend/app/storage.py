"""Call recordings: local disk in development, any S3-compatible bucket in production."""

import io
import os
import wave
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.config import get_settings


def pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def _s3():
    import boto3

    s = get_settings()
    return boto3.client("s3", region_name=s.s3_region, endpoint_url=s.s3_endpoint_url)


async def save_recording(call_id: str, wav_bytes: bytes) -> str:
    s = get_settings()
    key = f"recordings/{call_id}.wav"
    if s.s3_bucket:
        await run_in_threadpool(
            _s3().put_object, Bucket=s.s3_bucket, Key=key, Body=wav_bytes, ContentType="audio/wav", ServerSideEncryption="AES256"
        )
    else:
        path = Path(s.recordings_dir) / f"{call_id}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        await run_in_threadpool(path.write_bytes, wav_bytes)
    return key


async def recording_url_or_path(key: str) -> tuple[str | None, str | None]:
    """Return (presigned_url, local_path); exactly one is set."""
    s = get_settings()
    if s.s3_bucket:
        url = await run_in_threadpool(
            _s3().generate_presigned_url, "get_object", Params={"Bucket": s.s3_bucket, "Key": key}, ExpiresIn=300
        )
        return url, None
    path = Path(s.recordings_dir) / Path(key).name
    return None, str(path) if path.exists() else None


async def delete_recording(key: str) -> None:
    s = get_settings()
    if s.s3_bucket:
        await run_in_threadpool(_s3().delete_object, Bucket=s.s3_bucket, Key=key)
    else:
        path = Path(s.recordings_dir) / Path(key).name
        if path.exists():
            os.remove(path)
