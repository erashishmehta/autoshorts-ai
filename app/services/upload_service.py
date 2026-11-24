"""Validate and store uploaded source videos."""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import UPLOAD_DIR

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
CHUNK_SIZE = 1024 * 1024


async def save_uploaded_video(video: UploadFile, max_upload_size: int):
    """Validate an uploaded video and save it in chunks.

    Returns (job_id, video_path, total_size, original_filename).
    Removes a partial file if saving fails and always closes the upload.
    """
    original_filename = video.filename or ""
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        await video.close()
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    job_id = str(uuid.uuid4())
    video_path = UPLOAD_DIR / f"{job_id}{extension}"
    total_size = 0

    try:
        with video_path.open("wb") as destination:
            while True:
                chunk = await video.read(CHUNK_SIZE)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > max_upload_size:
                    raise HTTPException(
                        status_code=413,
                        detail="Video exceeds maximum upload size.",
                    )
                destination.write(chunk)
    except Exception:
        if video_path.exists():
            video_path.unlink()
        raise
    finally:
        await video.close()

    return job_id, video_path, total_size, original_filename
