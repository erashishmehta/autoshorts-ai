import re
import traceback

from app.config import CLIP_LENGTH, MAX_CLIPS
from app.utils.helpers import report
from app.services.ai_selector import select_clips_with_ai

# Number of transcript candidates sent to Ollama.
AI_CANDIDATE_LIMIT = 20

# Prevent adjacent/overlapping clips from being selected.
MIN_CLIP_GAP_SECONDS = 0.0


# =====================================================
# SCORE INTERESTING MOMENTS
# =====================================================


def score_clip(segments):
    text = " ".join(segment["text"] for segment in segments).lower()
    words = re.findall(r"\b\w+\b", text)

    hooks = [
        "secret",
        "important",
        "mistake",
        "amazing",
        "never",
        "best",
        "why",
        "how",
        "truth",
        "surprising",
        "incredible",
        "problem",
    ]

    hook_score = sum(text.count(word) for word in hooks)
    question_score = text.count("?")

    return len(words) + hook_score * 5 + question_score * 3


# =====================================================
# CLIP SELECTION HELPERS
# =====================================================


def _clip_key(clip):
    """Create a stable key from a clip's time range."""
    try:
        return (round(float(clip["start"]), 3), round(float(clip["end"]), 3))
    except (KeyError, TypeError, ValueError):
        return None


def _normalise_ai_selection(ai_result, candidates):
    """
    Match the AI result back to the original candidate objects.

    The expected ai_selector contract is a list of candidate dictionaries.
    Matching by start/end ensures that only clips actually offered to the AI
    can be selected. The function also tolerates dictionaries containing
    only start/end values.
    """
    if not isinstance(ai_result, list):
        return []

    candidate_by_key = {
        _clip_key(candidate): candidate
        for candidate in candidates
        if _clip_key(candidate) is not None
    }

    normalised = []

    for item in ai_result:
        if not isinstance(item, dict):
            continue

        key = _clip_key(item)
        if key is None:
            continue

        original = candidate_by_key.get(key)
        if original is not None:
            normalised.append(original)

    # De-duplicate while preserving the AI's returned order.
    unique = []
    seen = set()

    for clip in normalised:
        key = _clip_key(clip)
        if key not in seen:
            seen.add(key)
            unique.append(clip)

    return unique


def _remove_overlapping_clips(clips, max_clips=MAX_CLIPS):
    """Keep the supplied order, removing overlapping clips."""
    selected = []

    for candidate in clips:
        start = float(candidate["start"])
        end = float(candidate["end"])

        overlaps = any(
            start < float(existing["end"]) + MIN_CLIP_GAP_SECONDS
            and end > float(existing["start"]) - MIN_CLIP_GAP_SECONDS
            for existing in selected
        )

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= max_clips:
            break

    return selected


# =====================================================
# FIND BEST CLIPS
# =====================================================


def find_best_clips(segments, duration, progress_callback=None):
    report("Analyzing transcript for interesting moments...", progress_callback)

    clip_length = min(CLIP_LENGTH, duration)

    if clip_length < 5:
        raise ValueError("Video is too short to generate Shorts.")

    # Use overlapping windows to create multiple possible starting points.
    step = max(5, clip_length // 2)
    candidates = []
    start = 0.0
    candidate_number = 1

    # STEP 1: Generate candidate clips.
    while start + clip_length <= duration + 0.01:
        end = min(start + clip_length, duration)

        selected_segments = [
            segment
            for segment in segments
            if segment["end"] > start and segment["start"] < end
        ]

        if selected_segments:
            transcript = " ".join(
                segment["text"] for segment in selected_segments
            ).strip()

            candidates.append(
                {
                    "id": candidate_number,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "score": score_clip(selected_segments),
                    "text": transcript,
                }
            )
            candidate_number += 1

        start += step

    if not candidates:
        report("No transcript-based clip candidates were found.", progress_callback)
        return []

    report(
        f"Generated {len(candidates)} candidate clips.",
        progress_callback,
    )

    # STEP 2: Rank candidates for shortlist generation only.
    # The AI gets a varied shortlist drawn from the higher-scoring candidates.
    ranked_candidates = sorted(
        candidates,
        key=lambda clip: clip["score"],
        reverse=True,
    )
    ai_candidates = ranked_candidates[:AI_CANDIDATE_LIMIT]

    report(
        f"Sending {len(ai_candidates)} candidates to local AI "
        f"(Ollama model selection happens in ai_selector.py)...",
        progress_callback,
    )

    print("\n========== AI CANDIDATES ==========", flush=True)
    for candidate in ai_candidates:
        print(
            f"ID={candidate['id']} | "
            f"{candidate['start']:.1f}-{candidate['end']:.1f}s | "
            f"score={candidate['score']} | "
            f"text={candidate['text'][:180]!r}",
            flush=True,
        )
    print("===================================\n", flush=True)

    # STEP 3: AI selection.
    selected_clips = []

    try:
        report("Asking local AI to select the best moments...", progress_callback)
        ai_result = select_clips_with_ai(ai_candidates)

        print("\n========== AI SELECTION RESULT ==========", flush=True)
        print(f"AI raw result: {ai_result!r}", flush=True)
        print("=========================================\n", flush=True)

        selected_clips = _normalise_ai_selection(ai_result, ai_candidates)

        if selected_clips:
            report(
                f"AI successfully selected {len(selected_clips)} candidate(s).",
                progress_callback,
            )
        else:
            report(
                "AI returned no usable candidate clips. "
                "Rule-based fallback will be used.",
                progress_callback,
            )

    except Exception as error:
        print(
            f"[AutoShorts] AI selection raised an error: {error}",
            flush=True,
        )
        traceback.print_exc()
        report(
            "AI selection failed. Rule-based fallback will be used.",
            progress_callback,
        )

    # STEP 4: Fallback only when AI returns no valid selections.
    if not selected_clips:
        report("Selecting clips with rule-based fallback...", progress_callback)

        selected_clips = _remove_overlapping_clips(
            ranked_candidates,
            max_clips=MAX_CLIPS,
        )
        selection_method = "RULE-BASED FALLBACK"
    else:
        # Preserve AI preference order while enforcing overlap and clip limits.
        selected_clips = _remove_overlapping_clips(
            selected_clips,
            max_clips=MAX_CLIPS,
        )
        selection_method = "OLLAMA AI"

    # STEP 5: Sort chronologically for output filenames and playback order.
    selected_clips.sort(key=lambda clip: float(clip["start"]))

    print(f"\n[AutoShorts] FINAL SELECTION METHOD: {selection_method}", flush=True)
    for index, clip in enumerate(selected_clips, start=1):
        print(
            f"[AutoShorts] Final clip {index}: "
            f"ID={clip.get('id')} "
            f"{clip['start']:.1f}-{clip['end']:.1f}s "
            f"score={clip.get('score')}",
            flush=True,
        )

    report(
        f"Selected {len(selected_clips)} clips using {selection_method}.",
        progress_callback,
    )

    return selected_clips
