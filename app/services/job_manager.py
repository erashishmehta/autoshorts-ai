"""Background job execution, status tracking, and ZIP packaging."""

import traceback
from pathlib import Path

from app.config import OUTPUT_DIR
from app.services.video_processor import process_video
from app.services.archive_service import create_shorts_archive

# In-memory job status storage. Jobs reset when the server restarts.
jobs = {}


def generate_shorts(job_id, video_path):
    """Run the processing pipeline and package generated Shorts into a ZIP."""
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

        job_output = OUTPUT_DIR / job_id
        job_output.mkdir(parents=True, exist_ok=True)

        def update_progress(message):
            print(f"[JOB {job_id[:8]}] {message}", flush=True)
            jobs[job_id].update({"status": "processing", "message": message})

        print("Calling process_video()...", flush=True)
        clips = process_video(video_path, job_output, progress_callback=update_progress)
        print("Video processing completed!", flush=True)

        if not clips:
            raise ValueError("No Shorts were generated.")

        update_progress("Creating ZIP file for download...")
        zip_path = OUTPUT_DIR / f"{job_id}.zip"

        create_shorts_archive(clips, zip_path)

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
        # Remove the uploaded source video; retain generated clips and ZIP.
        try:
            source_path = Path(video_path)
            if source_path.exists():
                source_path.unlink()
                print("Temporary uploaded video removed.", flush=True)
        except OSError as cleanup_error:
            print(f"Upload cleanup warning: {cleanup_error}", flush=True)
