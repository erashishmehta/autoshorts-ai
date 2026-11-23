"""Subtitle timestamp formatting and SRT generation."""


def timestamp(seconds):
    """Format seconds as an SRT timestamp (HH:MM:SS,mmm)."""
    seconds = max(0, float(seconds))

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def create_srt(segments, clip, output_path, progress_callback=None):
    """Create an SRT file containing only transcript segments inside a clip."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    message = f"Creating subtitles: {output_path.name}"
    print(f"[AutoShorts] {message}", flush=True)
    if progress_callback:
        progress_callback(message)

    entries = []

    for segment in segments:
        start = max(float(segment["start"]), float(clip["start"]))
        end = min(float(segment["end"]), float(clip["end"]))

        if end <= start:
            continue

        relative_start = start - float(clip["start"])
        relative_end = end - float(clip["start"])
        text = str(segment.get("text", "")).strip()

        if not text:
            continue

        entries.append(
            f"{len(entries) + 1}\n"
            f"{timestamp(relative_start)} --> "
            f"{timestamp(relative_end)}\n"
            f"{text}\n"
        )

    output_path.write_text("\n".join(entries), encoding="utf-8")

    message = f"Subtitle file created: {output_path.name}"
    print(f"[AutoShorts] {message}", flush=True)
    if progress_callback:
        progress_callback(message)

    return output_path
