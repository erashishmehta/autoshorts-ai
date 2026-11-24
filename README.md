# AutoShorts AI

A local application that turns a long video into multiple vertical YouTube Shorts. It uses FastAPI for the local web app, FFmpeg for media processing, Faster-Whisper for transcription, OpenCV for face-aware crop positioning, and Ollama for optional local AI clip selection.

## Requirements

- macOS (the commands below use Homebrew)
- Python 3.11 or 3.12
- FFmpeg
- Ollama with the `qwen2.5:3b` model available locally

## Setup

### 1. Install system tools

```bash
brew install ffmpeg
```

Install Ollama from <https://ollama.com>, then download the model used by the application:

```bash
ollama pull qwen2.5:3b
```

Make sure the Ollama app/service is running before generating Shorts. The application calls its local API at `http://localhost:11434`.

### 2. Create and activate a virtual environment

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Start the application

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> in your browser.

The first transcription run may take longer because Faster-Whisper may need to download the selected model. The default model is `small`. To choose another Faster-Whisper model, set `WHISPER_MODEL` in the shell before starting the server, for example:

```bash
export WHISPER_MODEL=medium
uvicorn app.main:app --reload
```

## Application workflow

1. Upload a source video through the web page.
2. The app extracts audio and transcribes speech.
3. It identifies candidate moments and asks the local Ollama model to select clips. If AI selection fails, the clip selector can use its fallback behavior.
4. It creates an SRT subtitle file for each selected clip.
5. It renders each clip in 1080 × 1920 format, using face-aware crop positioning with a centre-crop fallback, and burns in subtitles.
6. It packages the generated MP4 files into a ZIP for download.

## Project structure

```text
app/
├── main.py
├── config.py
├── processor.py                 # Backward-compatible processor import
├── ai_selector.py               # Backward-compatible AI selector imports
├── routes/
│   └── video_routes.py          # FastAPI endpoints
├── services/
│   ├── ai_selector.py           # Ollama clip selection
│   ├── archive_service.py       # ZIP creation
│   ├── clip_selector.py         # Candidate generation and selection
│   ├── face_tracker.py          # Face detection / crop position
│   ├── job_manager.py           # Background job lifecycle
│   ├── subtitle_generator.py    # SRT generation
│   ├── transcription.py        # Faster-Whisper transcription
│   ├── upload_service.py        # Upload validation and storage
│   ├── video_processor.py       # Processing pipeline orchestration
│   └── video_renderer.py        # FFmpeg vertical rendering
├── templates/
│   └── index.html
└── utils/
    ├── ffmpeg.py
    └── helpers.py

uploads/                         # Temporary source uploads
outputs/                         # Generated Shorts and ZIP archives
```

## Notes and current limitations

- The app is designed to run locally; it does not require a paid transcription or LLM API.
- The upload limit is currently 2 GB. Supported upload extensions are `.mp4`, `.mov`, `.mkv`, and `.webm`.
- Job status is held in memory. Restarting the server clears the job list, so this version is intended for local use rather than multi-user production deployment.
- The current face tracker estimates one crop position for each clip; it is not continuous frame-by-frame face tracking.
- Generated files are stored in `outputs/`. The original uploaded source is removed after processing finishes.
