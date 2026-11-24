"""Shared application helpers."""


def report(message, progress_callback=None):
    """Log a progress message and forward it to an optional callback."""
    print(f"[AutoShorts] {message}", flush=True)
    if progress_callback:
        progress_callback(message)
