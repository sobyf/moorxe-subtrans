import re
from typing import List, Dict
from app.utils.logger import setup_logger

logger = setup_logger("srt-parser")

TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)

def parse_srt_content(text: str) -> List[Dict]:
    blocks = _split_blocks(text)
    subtitles = []

    for i, block in enumerate(blocks, start=1):
        try:
            subtitles.append(_parse_block(block, i))
        except ValueError as e:
            logger.warning(f"Skipping block #{i}: {e}")

    if not subtitles:
        raise ValueError("No valid subtitles found")

    return subtitles

def _split_blocks(text: str) -> List[str]:
    normalized = re.sub(r"\n{2,}", "\n\n", text.strip())
    return normalized.split("\n\n")

def _parse_block(block: str, fallback_index: int) -> Dict:
    lines = block.strip().split("\n")
    if len(lines) < 2: raise ValueError("Block too small")

    ts_idx = next((i for i, line in enumerate(lines) if "-->" in line), -1)
    if ts_idx == -1: raise ValueError("No timestamp")

    match = TIMESTAMP_PATTERN.search(lines[ts_idx])
    if not match: raise ValueError("Invalid timestamp format")

    text_lines = lines[ts_idx + 1:]
    if not text_lines: raise ValueError("Text missing")

    try:
        index = int(lines[0].strip())
    except:
        index = fallback_index

    return {
        "index": index,
        "start": match.group("start").replace(",", "."),
        "end": match.group("end").replace(",", "."),
        "text": "\n".join(text_lines).strip()
    }