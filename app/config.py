import os

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

# Storage
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
