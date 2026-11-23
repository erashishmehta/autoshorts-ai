"""Backward-compatible imports for the Ollama clip selector."""

from app.services.ai_selector import ask_local_ai, select_clips_with_ai

__all__ = ["ask_local_ai", "select_clips_with_ai"]
