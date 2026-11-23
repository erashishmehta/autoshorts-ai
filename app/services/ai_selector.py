
import json
import urllib.request

from app.config import MAX_CLIPS


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"


def ask_local_ai(candidates):

    prompt = f"""
You are an expert YouTube Shorts editor.

Analyze the following video clip candidates.

Select up to {MAX_CLIPS} clips that have:

- A strong opening hook.
- An interesting or surprising idea.
- A complete thought.
- High audience engagement potential.
- A satisfying ending.

Avoid:
- Incomplete sentences.
- Repetitive content.
- Clips requiring missing context.
- Weak or uninteresting moments.

Important:
- Choose clips based on transcript meaning, not just keywords.
- Prefer clips that make sense independently.
- Avoid selecting overlapping clips.

Return ONLY valid JSON:

{{
    "selected_ids": [0, 2, 4]
}}

Candidates:

{json.dumps(candidates, ensure_ascii=False)}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2
        }
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=180) as response:

        result = json.loads(response.read())

    answer = json.loads(result["response"])

    selected_ids = answer.get("selected_ids", [])

    if not isinstance(selected_ids, list):
        raise ValueError("Invalid AI response: selected_ids must be a list.")

    return selected_ids


def select_clips_with_ai(candidates):

    if not candidates:
        return []

    try:

        print("[AutoShorts] Asking Ollama to select clips...", flush=True)

        selected_ids = ask_local_ai(candidates)

        selected = []

        seen = set()

        for index in selected_ids:

            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or index >= len(candidates)
                or index in seen
            ):
                continue

            seen.add(index)
            selected.append(candidates[index])

        # Sort chronologically
        selected.sort(key=lambda x: x["start"])

        # Prevent overlapping clips
        final = []

        for clip in selected:

            overlap = any(
                clip["start"] < item["end"]
                and clip["end"] > item["start"]
                for item in final
            )

            if not overlap:
                final.append(clip)

            if len(final) >= MAX_CLIPS:
                break

        print(
            f"[AutoShorts] Ollama selected {len(final)} clips.",
            flush=True
        )

        return final

    except Exception as error:

        print(
            f"[AutoShorts] AI selection failed: {error}",
            flush=True
        )

        return []
