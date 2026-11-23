"""Backward-compatible imports for the video processing pipeline."""

from app.services.video_processor import extract_audio, process_video, report

__all__ = ["extract_audio", "process_video", "report"]
