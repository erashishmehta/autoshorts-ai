import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"


def ask_local_ai(candidates):
    prompt = f"""
You are an expert YouTube Shorts editor.

Analyze these candidate video clips.

Choose up to 5 clips that have:
- A strong opening hook
- An interesting or surprising idea
- A complete thought
- High audience engagement potential
- A satisfying ending

Avoid incomplete sentences and clips that need
missing context.

Return ONLY JSON in this format:

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
        "options": {"temperature": 0.2},
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read())

    answer = json.loads(result["response"])

    return answer["selected_ids"]


def select_clips_with_ai(candidates):
    if not candidates:
        return []

    try:
        selected_ids = ask_local_ai(candidates)

        selected = [
            candidates[i]
            for i in selected_ids
            if isinstance(i, int) and 0 <= i < len(candidates)
        ]

        # Prevent overlapping clips
        final = []

        for clip in sorted(selected, key=lambda x: x["start"]):
            overlap = any(
                clip["start"] < item["end"] and clip["end"] > item["start"]
                for item in final
            )

            if not overlap:
                final.append(clip)

        return final[:5]

    except Exception as error:
        print("AI selection failed:", error)
        return []
