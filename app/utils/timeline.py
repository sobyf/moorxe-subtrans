from typing import List, Dict
from app.utils.logger import setup_logger

logger = setup_logger("srt-timeline")


# ----------------------------------
# Public API
# ----------------------------------

def normalize_subtitle_timeline(subtitles: List[Dict]) -> List[Dict]:
    """
    Converts timestamp strings into milliseconds and validates timeline.

    Adds fields:
    - start_ms
    - end_ms
    - duration_ms

    Validates:
    - start < end
    - no negative durations
    """

    logger.info("Starting subtitle timeline normalization")

    normalized = []

    previous_end = None

    for i, subtitle in enumerate(subtitles, start=1):
        try:
            start_ms = timestamp_to_ms(subtitle["start"])
            end_ms = timestamp_to_ms(subtitle["end"])

            if start_ms >= end_ms:
                raise ValueError("Start time must be less than end time")

            duration = end_ms - start_ms

            # Optional overlap detection (professional feature)
            if previous_end is not None and start_ms < previous_end:
                logger.warning(
                    f"Overlap detected at subtitle #{subtitle['index']}"
                )

            previous_end = end_ms

            subtitle["start_ms"] = start_ms
            subtitle["end_ms"] = end_ms
            subtitle["duration_ms"] = duration

            normalized.append(subtitle)

        except Exception as exc:
            logger.warning(
                f"Skipping invalid timing block #{subtitle.get('index')}: {exc}"
            )

    if not normalized:
        raise ValueError("No valid subtitle timelines produced")

    logger.info(f"Timeline normalized for {len(normalized)} subtitles")

    return normalized


# ----------------------------------
# Internal Helpers
# ----------------------------------

def timestamp_to_ms(timestamp: str) -> int:
    """
    Converts SRT timestamp into milliseconds.

    Format:
    HH:MM:SS.mmm

    Example:
    00:01:02.500 -> 62500 ms
    """

    try:
        time_part, ms_part = timestamp.split(".")
        hours, minutes, seconds = time_part.split(":")

        total_ms = (
            int(hours) * 3600000 +
            int(minutes) * 60000 +
            int(seconds) * 1000 +
            int(ms_part)
        )

        return total_ms

    except Exception:
        raise ValueError(f"Invalid timestamp format: {timestamp}")
