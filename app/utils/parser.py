import re
from typing import List, Dict
from app.utils.logger import setup_logger

logger = setup_logger("srt-parser")


# ----------------------------------
# Regex Patterns
# ----------------------------------

TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)



# ----------------------------------
# Public API
# ----------------------------------

def parse_srt_content(text: str) -> List[Dict]:
    """
    Parses normalized SRT text into structured subtitle blocks.

    Returns:
        List of subtitle dictionaries:
        {
            index: int,
            start: str,
            end: str,
            text: str
        }
    """

    logger.info("Starting SRT parsing pipeline")

    blocks = _split_blocks(text)

    subtitles = []

    for block_number, block in enumerate(blocks, start=1):
        try:
            subtitle = _parse_block(block, block_number)
            subtitles.append(subtitle)
        except ValueError as e:
            logger.warning(f"Skipping invalid subtitle block #{block_number}: {e}")

    logger.info(f"Parsed {len(subtitles)} valid subtitle blocks")

    if not subtitles:
        raise ValueError("No valid subtitles found in SRT file")

    return subtitles


# ----------------------------------
# Internal Helpers
# ----------------------------------

def _split_blocks(text: str) -> List[str]:
    """
    Splits SRT text into raw blocks using empty lines.
    """

    logger.debug("Splitting SRT into blocks")

    # Normalize excessive spacing
    normalized = re.sub(r"\n{2,}", "\n\n", text.strip())

    return normalized.split("\n\n")


def _parse_block(block: str, fallback_index: int) -> Dict:
    """
    Parses single subtitle block.

    Supports:
    - Missing index
    - Corrupted numbering
    """

    lines = block.strip().split("\n")

    if len(lines) < 2:
        raise ValueError("Block too small")

    # ----------------------------------
    # Detect timestamp line
    # ----------------------------------

    timestamp_line_index = _find_timestamp_line(lines)

    timestamp_line = lines[timestamp_line_index]

    match = TIMESTAMP_PATTERN.search(timestamp_line)

    if not match:
        raise ValueError("Timestamp format invalid")

    start = _normalize_timestamp(match.group("start"))
    end = _normalize_timestamp(match.group("end"))

    # ----------------------------------
    # Extract subtitle text
    # ----------------------------------

    text_lines = lines[timestamp_line_index + 1 :]

    if not text_lines:
        raise ValueError("Subtitle text missing")

    subtitle_text = "\n".join(text_lines).strip()

    # ----------------------------------
    # Detect index (optional)
    # ----------------------------------

    index = _parse_index(lines[0], fallback_index)

    return {
        "index": index,
        "start": start,
        "end": end,
        "text": subtitle_text
    }


def _find_timestamp_line(lines: List[str]) -> int:
    """
    Finds timestamp line position inside block.
    """

    for i, line in enumerate(lines):
        if "-->" in line:
            return i

    raise ValueError("Timestamp line not found")


def _parse_index(first_line: str, fallback: int) -> int:
    """
    Parses subtitle index or uses fallback.
    """

    try:
        return int(first_line.strip())
    except ValueError:
        logger.debug("Invalid or missing subtitle index, using fallback")
        return fallback


def _normalize_timestamp(timestamp: str) -> str:
    """
    Converts comma timestamps to dot format.

    Example:
    00:00:01,500 -> 00:00:01.500
    """

    return timestamp.replace(",", ".")
