from typing import List, Dict
from app.utils.logger import setup_logger

logger = setup_logger("srt-timeline")

def normalize_subtitle_timeline(subtitles: List[Dict]) -> List[Dict]:
    normalized = []
    previous_end = None

    for sub in subtitles:
        try:
            start_ms = timestamp_to_ms(sub["start"])
            end_ms = timestamp_to_ms(sub["end"])

            if start_ms >= end_ms:
                raise ValueError("Start >= End")

            if previous_end is not None and start_ms < previous_end:
                logger.warning(f"Overlap at #{sub['index']}")

            previous_end = end_ms
            sub.update({"start_ms": start_ms, "end_ms": end_ms, "duration_ms": end_ms - start_ms})
            normalized.append(sub)

        except Exception as exc:
            logger.warning(f"Skipping timing block #{sub.get('index')}: {exc}")

    if not normalized:
        raise ValueError("No valid timelines")

    return normalized

def timestamp_to_ms(ts: str) -> int:
    try:
        hms, ms = ts.split(".")
        h, m, s = map(int, hms.split(":"))
        return h * 3600000 + m * 60000 + s * 1000 + int(ms)
    except:
        raise ValueError(f"Invalid TS: {ts}")