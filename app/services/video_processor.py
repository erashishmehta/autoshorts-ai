import time
import traceback
from pathlib import Path


from app.services.transcription import get_whisper_model, transcribe_audio
from app.utils.helpers import report
from app.services.clip_selector import find_best_clips
from app.services.face_tracker import detect_face_crop_x
from app.services.subtitle_generator import create_srt
from app.services.video_renderer import generate_video
from app.utils.ffmpeg import (
    FFMPEG_BIN,
    check_ffmpeg,
    get_duration,
    has_audio_stream,
    run_command,
)

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
        segments = transcribe_audio(
            model=model,
            audio_path=audio_path,
            duration=duration,
            progress_callback=progress_callback,
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

            report(
                f"Generating Short {index}/{total_clips}...",
                progress_callback,
            )

            create_srt(segments, clip, subtitle_file, progress_callback)

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
        traceback.print_exc()
        raise
