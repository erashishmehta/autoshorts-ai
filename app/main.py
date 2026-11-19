import uuid
import zipfile
import traceback

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException

from fastapi.responses import HTMLResponse, FileResponse

from app.processor import process_video
from app.config import MAX_UPLOAD_SIZE

# =====================================================
# APPLICATION SETUP
# =====================================================

app = FastAPI(
    title="AutoShorts AI", description="Automatically generate YouTube Shorts"
)

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

TEMPLATE = BASE_DIR / "app" / "templates" / "index.html"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================
# JOB STORAGE
# =====================================================

jobs = {}


# =====================================================
# SUPPORTED VIDEO FORMATS
# =====================================================

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


# =====================================================
# BACKGROUND VIDEO PROCESSING
# =====================================================


def generate_shorts(job_id, video_path):

    print("\n========== JOB STARTED ==========", flush=True)

    print(f"Job ID: {job_id}", flush=True)

    print(f"Video: {video_path}", flush=True)

    try:

        jobs[job_id].update(
            {
                "status": "processing",
                "message": "Starting video processing...",
                "progress": 0,
            }
        )

        # Create output directory

        job_output = OUTPUT_DIR / job_id

        job_output.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------
        # PROGRESS CALLBACK
        # ---------------------------------------------

        def update_progress(message):

            print(f"[JOB {job_id[:8]}] {message}", flush=True)

            jobs[job_id].update({"status": "processing", "message": message})

        # ---------------------------------------------
        # START PROCESSING
        # ---------------------------------------------

        print("Calling process_video()...", flush=True)

        clips = process_video(video_path, job_output, progress_callback=update_progress)

        print("Video processing completed!", flush=True)

        if not clips:
            raise ValueError("No Shorts were generated.")

        # ---------------------------------------------
        # CREATE ZIP FILE
        # ---------------------------------------------

        update_progress("Creating ZIP file for download...")

        zip_path = OUTPUT_DIR / f"{job_id}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:

            for clip in clips:

                if not Path(clip).exists():
                    raise FileNotFoundError(f"Generated video not found: {clip}")

                archive.write(clip, arcname=Path(clip).name)

        # ---------------------------------------------
        # JOB COMPLETED
        # ---------------------------------------------

        jobs[job_id].update(
            {
                "status": "completed",
                "message": "Your Shorts are ready!",
                "progress": 100,
                "count": len(clips),
                "download": f"/download/{job_id}",
            }
        )

        print(f"Successfully generated {len(clips)} Shorts!", flush=True)

        print("========== JOB COMPLETED ==========\n", flush=True)

    except Exception as error:

        print("\n========== JOB FAILED ==========", flush=True)

        traceback.print_exc()

        jobs[job_id].update({"status": "failed", "message": str(error), "progress": 0})

        print("========== JOB FAILED ==========\n", flush=True)

    finally:

        # Remove original uploaded video to save disk space.
        # Keep generated videos and ZIP file.

        try:

            if Path(video_path).exists():
                Path(video_path).unlink()

                print("Temporary uploaded video removed.", flush=True)

        except OSError as cleanup_error:

            print(f"Upload cleanup warning: {cleanup_error}", flush=True)


# =====================================================
# HOME PAGE
# =====================================================


@app.get("/", response_class=HTMLResponse)
def home():

    if not TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Frontend template not found.")

    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))


# =====================================================
# VIDEO UPLOAD API
# =====================================================


@app.post("/api/generate")
async def upload_video(
    background_tasks: BackgroundTasks, video: UploadFile = File(...)
):

    print("\n========== VIDEO UPLOAD ==========", flush=True)

    # Check file extension

    extension = Path(video.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(status_code=400, detail="Unsupported video format.")

    job_id = str(uuid.uuid4())

    video_path = UPLOAD_DIR / f"{job_id}{extension}"

    total_size = 0

    try:

        # Save video in chunks.
        # This avoids loading the entire upload into RAM.

        with video_path.open("wb") as destination:

            while True:

                chunk = await video.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE:

                    raise HTTPException(
                        status_code=413, detail="Video exceeds maximum upload size."
                    )

                destination.write(chunk)

    except Exception:

        if video_path.exists():
            video_path.unlink()

        raise

    finally:

        await video.close()

    print(f"Video uploaded: {video.filename}", flush=True)

    print(f"File size: {total_size / (1024 * 1024):.2f} MB", flush=True)

    print(f"Job ID: {job_id}", flush=True)

    # Initialize job status

    jobs[job_id] = {
        "status": "queued",
        "message": "Video uploaded successfully.",
        "progress": 0,
        "count": 0,
        "download": None,
    }

    print("Background task is being scheduled!", flush=True)

    background_tasks.add_task(generate_shorts, job_id, video_path)

    print("Background task scheduled!", flush=True)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Video uploaded successfully.",
    }


# =====================================================
# JOB STATUS API
# =====================================================


@app.get("/api/status/{job_id}")
def get_status(job_id: str):

    if job_id not in jobs:

        raise HTTPException(status_code=404, detail="Job not found.")

    return jobs[job_id]


# =====================================================
# DOWNLOAD GENERATED SHORTS
# =====================================================


@app.get("/download/{job_id}")
def download_shorts(job_id: str):

    if job_id not in jobs:

        raise HTTPException(status_code=404, detail="Job not found.")

    if jobs[job_id]["status"] != "completed":

        raise HTTPException(
            status_code=409, detail="Video generation is not completed yet."
        )

    zip_path = OUTPUT_DIR / f"{job_id}.zip"

    if not zip_path.exists():

        raise HTTPException(status_code=404, detail="Download file not found.")

    return FileResponse(
        path=zip_path, media_type="application/zip", filename="autoshorts.zip"
    )


# =====================================================
# HEALTH CHECK
# =====================================================


@app.get("/api/health")
def health_check():

    return {"status": "healthy", "application": "AutoShorts AI"}
