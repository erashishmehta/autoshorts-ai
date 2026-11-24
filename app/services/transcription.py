"""Whisper model loading and audio transcription service."""

import time
from pathlib import Path

from faster_whisper import WhisperModel

from app.utils.helpers import report as _report

from app.config import (
    WHISPER_MODEL,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    CPU_THREADS,
    NUM_WORKERS,
)

_whisper_model = None


def load_whisper():
    """Create the configured Faster-Whisper model."""
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
    """Return the cached Whisper model, loading it only once per process."""
    global _whisper_model

    if _whisper_model is None:
        _whisper_model = load_whisper()

    return _whisper_model


def transcribe_audio(model, audio_path, duration, progress_callback=None):
    """Transcribe a WAV file and return plain dictionaries for each segment."""
    audio_path = Path(audio_path)
    _report("Starting AI transcription...", progress_callback)

    whisper_segments, info = model.transcribe(
        str(audio_path),
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    _report(f"Detected language: {info.language}", progress_callback)
    _report("Transcribing audio. Please wait...", progress_callback)

    segments = []
    last_log_time = time.time()

    for index, segment in enumerate(whisper_segments, start=1):
        segments.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
            }
        )

        current_time = time.time()

        if index % 50 == 0 or current_time - last_log_time >= 5:
            percentage = min(100, int(segment.end / duration * 100)) if duration else 0
            _report(
                f"Transcribed {index} segments... "
                f"({percentage}% of audio timeline)",
                progress_callback,
            )
            last_log_time = current_time

    _report(
        f"Transcription completed! Total segments: {len(segments)}",
        progress_callback,
    )

    if not segments:
        raise ValueError("No speech detected in this video.")

    return segments
