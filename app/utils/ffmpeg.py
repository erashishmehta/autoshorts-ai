import os
import re
import shutil
import subprocess
from pathlib import Path


# Keep your existing local Mac paths. You can override them with
# AUTOSHORTS_FFMPEG and AUTOSHORTS_FFPROBE environment variables.
FFMPEG_BIN = os.getenv(
    "AUTOSHORTS_FFMPEG",
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
)
FFPROBE_BIN = os.getenv(
    "AUTOSHORTS_FFPROBE",
    shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe",
)


def run_command(command, cwd=None):
    """Run a subprocess command and raise a useful error on failure."""
    print(
        "[AutoShorts] Running command:",
        " ".join(str(item) for item in command),
        flush=True,
    )

    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[AutoShorts] COMMAND ERROR:", result.stderr, flush=True)
        raise RuntimeError(result.stderr[-5000:])

    return result


def check_ffmpeg():
    """Verify FFmpeg exists and includes the subtitles/libass filter."""
    if not Path(FFMPEG_BIN).is_file():
        raise RuntimeError(
            f"FFmpeg executable not found: {FFMPEG_BIN}. "
            "Check your ffmpeg-full installation."
        )

    result = run_command([FFMPEG_BIN, "-hide_banner", "-filters"])
    filters = result.stdout + result.stderr

    if not re.search(r"\bsubtitles\b", filters):
        raise RuntimeError(
            "FFmpeg does not have the subtitles filter. "
            "Install an FFmpeg build with libass support."
        )

    print("[AutoShorts] FFmpeg subtitles support verified!", flush=True)


def get_duration(video_path):
    """Return video duration in seconds using FFprobe."""
    result = run_command(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    return float(result.stdout.strip())


def has_audio_stream(video_path):
    """Return True when the input video contains an audio stream."""
    result = run_command(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
    )
    return bool(result.stdout.strip())
