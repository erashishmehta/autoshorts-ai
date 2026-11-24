"""Create downloadable ZIP archives from generated Shorts."""

from pathlib import Path
import zipfile


def create_shorts_archive(clips, archive_path):
    """Package generated video clips into a ZIP and return its path.

    Raises FileNotFoundError if any generated clip is missing. The archive is
    written only after each clip has been validated.
    """
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    clip_paths = [Path(clip) for clip in clips]
    if not clip_paths:
        raise ValueError("No Shorts were provided for the ZIP archive.")

    for clip_path in clip_paths:
        if not clip_path.is_file():
            raise FileNotFoundError(f"Generated video not found: {clip_path}")

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for clip_path in clip_paths:
            archive.write(clip_path, arcname=clip_path.name)

    return archive_path
