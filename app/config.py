"""Central application configuration and project storage paths."""

import os
from pathlib import Path

# Project directories
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
TEMPLATE_FILE = TEMPLATE_DIR / "index.html"

# Create storage directories when the application is imported.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# AI configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# CPU optimization
CPU_THREADS = 4
NUM_WORKERS = 1

# Video configuration
CLIP_LENGTH = 45
MAX_CLIPS = 5
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Storage limits
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
