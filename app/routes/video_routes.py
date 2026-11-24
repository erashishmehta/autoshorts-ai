"""HTTP routes and background jobs for video upload and Shorts generation."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.config import MAX_UPLOAD_SIZE, OUTPUT_DIR, TEMPLATE_FILE
from app.services.job_manager import generate_shorts, jobs
from app.services.upload_service import save_uploaded_video

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home():
    if not TEMPLATE_FILE.exists():
        raise HTTPException(status_code=500, detail="Frontend template not found.")
    return HTMLResponse(TEMPLATE_FILE.read_text(encoding="utf-8"))


@router.post("/api/generate")
async def upload_video(
    background_tasks: BackgroundTasks, video: UploadFile = File(...)
):
    print("\n========== VIDEO UPLOAD ==========", flush=True)

    job_id, video_path, total_size, original_filename = await save_uploaded_video(
        video, MAX_UPLOAD_SIZE
    )

    print(f"Video uploaded: {original_filename}", flush=True)
    print(f"File size: {total_size / (1024 * 1024):.2f} MB", flush=True)
    print(f"Job ID: {job_id}", flush=True)

    jobs[job_id] = {
        "status": "queued",
        "message": "Video uploaded successfully.",
        "progress": 0,
        "count": 0,
        "download": None,
    }

    background_tasks.add_task(generate_shorts, job_id, video_path)
    print("Background task scheduled!", flush=True)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Video uploaded successfully.",
    }


@router.get("/api/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return jobs[job_id]


@router.get("/download/{job_id}")
def download_shorts(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    if jobs[job_id]["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Video generation is not completed yet.",
        )

    zip_path = OUTPUT_DIR / f"{job_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Download file not found.")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename="autoshorts.zip",
    )


@router.get("/api/health")
def health_check():
    return {"status": "healthy", "application": "AutoShorts AI"}
