"""FFmpeg-based vertical video rendering."""

from pathlib import Path

from app.services.face_tracker import detect_face_crop_x
from app.utils.ffmpeg import FFMPEG_BIN, run_command


def report(message, progress_callback=None):
    print(f"[AutoShorts] {message}", flush=True)
    if progress_callback:
        progress_callback(message)


def generate_video(
    video_path,
    clip,
    subtitle_file,
    output_file,
    output_dir,
    progress_callback=None,
):
    """Render one vertical Short with burned-in subtitles."""
    video_path = Path(video_path)
    subtitle_file = Path(subtitle_file)
    output_file = Path(output_file)
    output_dir = Path(output_dir)

    report(f"Exporting {output_file.name} with FFmpeg...", progress_callback)

    # Keep the relative subtitle filename and run FFmpeg from output_dir.
    subtitle_name = subtitle_file.name

    crop_x = detect_face_crop_x(video_path, clip, progress_callback)

    if crop_x is None:
        # Explicitly centre the crop when no face can be detected.
        crop_expression = "(in_w-1080)/2"
        report("Using centre crop fallback.", progress_callback)
    else:
        crop_expression = str(crop_x)

    filter_value = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        f"crop=1080:1920:{crop_expression}:(in_h-1920)/2,"
        f"subtitles=filename={subtitle_name}"
    )

    run_command(
        [
            FFMPEG_BIN,
            "-y",
            "-ss",
            str(clip["start"]),
            "-i",
            str(video_path),
            "-t",
            str(clip["end"] - clip["start"]),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            filter_value,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-threads",
            "4",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_file),
        ],
        cwd=output_dir,
    )

    if not output_file.exists():
        raise RuntimeError(f"FFmpeg failed to create {output_file.name}")

    if output_file.stat().st_size == 0:
        raise RuntimeError(f"Generated video is empty: {output_file.name}")

    report(f"Video created successfully: {output_file.name}", progress_callback)
    return output_file
