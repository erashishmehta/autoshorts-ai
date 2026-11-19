import os
import re
import time
import shutil
import subprocess

from pathlib import Path
from faster_whisper import WhisperModel

from app.config import (
    WHISPER_MODEL,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    CPU_THREADS,
    NUM_WORKERS,
    CLIP_LENGTH,
    MAX_CLIPS,
)

# =====================================================
# FFMPEG CONFIGURATION
# =====================================================

# Use FFmpeg Full because it includes libass subtitles.
# You can override this using AUTOSHORTS_FFMPEG.

FFMPEG_BIN = os.getenv("AUTOSHORTS_FFMPEG", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")

FFPROBE_BIN = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


# =====================================================
# GLOBAL WHISPER MODEL
# =====================================================

_whisper_model = None


# =====================================================
# PROGRESS REPORTING
# =====================================================


def report(message, progress_callback=None):

    print(f"[AutoShorts] {message}", flush=True)

    if progress_callback:
        progress_callback(message)


# =====================================================
# RUN COMMAND
# =====================================================


def run_command(command, cwd=None):

    print(
        "[AutoShorts] Running command:", " ".join(str(x) for x in command), flush=True
    )

    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)

    if result.returncode != 0:

        print("[AutoShorts] COMMAND ERROR:", result.stderr, flush=True)

        raise RuntimeError(result.stderr[-5000:])

    return result


# =====================================================
# CHECK FFMPEG SUBTITLE SUPPORT
# =====================================================


def check_ffmpeg():

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


# =====================================================
# LOAD WHISPER MODEL
# =====================================================


def load_whisper():

    print(f"[AutoShorts] Loading Whisper model: {WHISPER_MODEL}", flush=True)

    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
        num_workers=NUM_WORKERS,
    )

    print("[AutoShorts] Whisper model loaded successfully!", flush=True)

    return model


def get_whisper_model():

    global _whisper_model

    if _whisper_model is None:
        _whisper_model = load_whisper()

    return _whisper_model


# =====================================================
# GET VIDEO DURATION
# =====================================================


def get_duration(video_path):

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


# =====================================================
# CHECK AUDIO STREAM
# =====================================================


def has_audio_stream(video_path):

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


# =====================================================
# EXTRACT AUDIO
# =====================================================


def extract_audio(video_path, output_dir, progress_callback=None):

    audio_path = output_dir / "audio.wav"

    report("Checking video audio stream...", progress_callback)

    if not has_audio_stream(video_path):

        raise ValueError(
            "This video does not contain an audio stream. "
            "Please upload a video with audio."
        )

    report("Audio stream detected. Extracting audio...", progress_callback)

    run_command(
        [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(video_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ]
    )

    if not audio_path.exists() or audio_path.stat().st_size == 0:

        raise RuntimeError("Audio extraction failed.")

    report("Audio extraction completed successfully!", progress_callback)

    return audio_path


# =====================================================
# FORMAT SUBTITLE TIMESTAMP
# =====================================================


def timestamp(seconds):

    seconds = max(0, seconds)

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:" f"{secs:02},{milliseconds:03}"


# =====================================================
# SCORE INTERESTING MOMENTS
# =====================================================


def score_clip(segments):

    text = " ".join(s["text"] for s in segments).lower()

    words = re.findall(r"\b\w+\b", text)

    hooks = [
        "secret",
        "important",
        "mistake",
        "amazing",
        "never",
        "best",
        "why",
        "how",
        "truth",
        "surprising",
        "incredible",
        "problem",
    ]

    hook_score = sum(text.count(word) for word in hooks)

    question_score = text.count("?")

    return len(words) + hook_score * 5 + question_score * 3


# =====================================================
# FIND BEST CLIPS
# =====================================================


def find_best_clips(segments, duration, progress_callback=None):

    report("Analyzing transcript for interesting moments...", progress_callback)

    clip_length = min(CLIP_LENGTH, duration)

    if clip_length < 5:

        raise ValueError("Video is too short to generate Shorts.")

    step = max(5, clip_length // 2)

    candidates = []

    start = 0

    while start + clip_length <= duration + 0.01:

        end = min(start + clip_length, duration)

        selected = [s for s in segments if s["end"] > start and s["start"] < end]

        if selected:

            score = score_clip(selected)

            candidates.append({"start": start, "end": end, "score": score})

        start += step

    report(f"Analyzed {len(candidates)} candidate clips.", progress_callback)

    candidates.sort(key=lambda x: x["score"], reverse=True)

    selected_clips = []

    for candidate in candidates:

        overlaps = any(
            candidate["start"] < clip["end"] and candidate["end"] > clip["start"]
            for clip in selected_clips
        )

        if not overlaps:

            selected_clips.append(candidate)

        if len(selected_clips) >= MAX_CLIPS:
            break

    selected_clips.sort(key=lambda x: x["start"])

    return selected_clips


# =====================================================
# CREATE SRT SUBTITLE FILE
# =====================================================


def create_srt(segments, clip, output_path, progress_callback=None):

    report(f"Creating subtitles: {output_path.name}", progress_callback)

    entries = []

    for segment in segments:

        start = max(segment["start"], clip["start"])

        end = min(segment["end"], clip["end"])

        if end <= start:
            continue

        relative_start = start - clip["start"]
        relative_end = end - clip["start"]

        text = segment["text"].strip()

        if not text:
            continue

        entries.append(
            f"{len(entries) + 1}\n"
            f"{timestamp(relative_start)} --> "
            f"{timestamp(relative_end)}\n"
            f"{text}\n"
        )

    output_path.write_text("\n".join(entries), encoding="utf-8")

    report(f"Subtitle file created: {output_path.name}", progress_callback)


# =====================================================
# GENERATE VERTICAL VIDEO
# =====================================================


def generate_video(
    video_path, clip, subtitle_file, output_file, output_dir, progress_callback=None
):

    report(f"Exporting {output_file.name} with FFmpeg...", progress_callback)

    # IMPORTANT:
    # Use a relative subtitle filename.
    # Run FFmpeg from output_dir.
    # This avoids absolute-path escaping problems.

    subtitle_name = subtitle_file.name

    filter_value = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
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


# =====================================================
# MAIN VIDEO PROCESSING
# =====================================================


def process_video(video_path, output_dir, progress_callback=None):

    print("\n========== PROCESS VIDEO STARTED ==========", flush=True)

    video_path = Path(video_path).resolve()

    output_dir = Path(output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    try:

        # STEP 1: CHECK FFMPEG

        report("Checking FFmpeg configuration...", progress_callback)

        check_ffmpeg()

        # STEP 2: LOAD WHISPER

        report("Loading Whisper model...", progress_callback)

        model = get_whisper_model()

        # STEP 3: VIDEO DURATION

        report("Checking video duration...", progress_callback)

        duration = get_duration(video_path)

        report(f"Video duration: {duration / 60:.1f} minutes", progress_callback)

        # STEP 4: AUDIO EXTRACTION

        audio_path = extract_audio(video_path, output_dir, progress_callback)

        # STEP 5: TRANSCRIPTION

        report("Starting AI transcription...", progress_callback)

        whisper_segments, info = model.transcribe(
            str(audio_path),
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        report(f"Detected language: {info.language}", progress_callback)

        report("Transcribing audio. Please wait...", progress_callback)

        segments = []

        last_log_time = time.time()

        for i, s in enumerate(whisper_segments, start=1):

            segments.append(
                {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
            )

            current_time = time.time()

            if i % 50 == 0 or current_time - last_log_time >= 5:

                percentage = min(100, int(s.end / duration * 100))

                report(
                    f"Transcribed {i} segments... "
                    f"({percentage}% of audio timeline)",
                    progress_callback,
                )

                last_log_time = current_time

        report(
            f"Transcription completed! " f"Total segments: {len(segments)}",
            progress_callback,
        )

        if not segments:

            raise ValueError("No speech detected in this video.")

        # STEP 6: FIND INTERESTING MOMENTS

        report("Finding interesting moments...", progress_callback)

        clips = find_best_clips(segments, duration, progress_callback)

        if not clips:

            raise ValueError("Could not find suitable clips.")

        report(f"Found {len(clips)} suitable clips.", progress_callback)

        # STEP 7: GENERATE SHORTS

        generated = []

        total_clips = len(clips)

        for index, clip in enumerate(clips, start=1):

            name = f"short_{index:02}"

            subtitle_file = output_dir / f"{name}.srt"

            output_file = output_dir / f"{name}.mp4"

            report(f"Generating Short {index}/{total_clips}...", progress_callback)

            # CREATE SUBTITLES

            create_srt(segments, clip, subtitle_file, progress_callback)

            # GENERATE VIDEO

            generated_video = generate_video(
                video_path,
                clip,
                subtitle_file,
                output_file,
                output_dir,
                progress_callback,
            )

            generated.append(generated_video)

            report(
                f"Short {index}/{total_clips} completed successfully!",
                progress_callback,
            )

        # STEP 8: FINISH

        report("All Shorts generated successfully!", progress_callback)

        print("========== PROCESS VIDEO FINISHED ==========\n", flush=True)

        return generated

    except Exception:

        print("\n========== PROCESSOR ERROR ==========", flush=True)

        import traceback

        traceback.print_exc()

        raise
