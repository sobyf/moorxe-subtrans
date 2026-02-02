from typing import Optional
from app.utils.logger import setup_logger


# Dedicated logger for decoding pipeline
logger = setup_logger("srt-decoder")


# ----------------------------------
# Encoding Constants
# ----------------------------------

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"

FALLBACK_ENCODINGS = (
    "windows-1256",  # Arabic / Persian
    "windows-1252",  # Western European
    "iso-8859-1"
)


# ----------------------------------
# Public API
# ----------------------------------

def decode_subtitle_bytes(raw_bytes: bytes) -> str:
    """
    Decodes raw subtitle bytes into normalized Unicode text.

    Decoding strategy:
    1. Detect and handle BOM (UTF-8 / UTF-16)
    2. Attempt UTF-8 strict decoding
    3. Attempt UTF-16 fallback
    4. Attempt regional fallback encodings
    5. Normalize line endings
    6. Remove hidden control characters

    Raises:
        ValueError: If decoding fails for all supported encodings.
    """

    logger.info("Starting subtitle byte decoding pipeline")

    if not raw_bytes:
        logger.error("Uploaded subtitle file is empty")
        raise ValueError("Uploaded subtitle file is empty")

    # -------------------------------
    # BOM Detection
    # -------------------------------

    encoding_hint = _detect_bom(raw_bytes)

    if encoding_hint:
        logger.info(f"BOM detected: {encoding_hint}")
        try:
            text = raw_bytes.decode(encoding_hint)
            return _normalize_text(text)
        except UnicodeDecodeError:
            logger.warning("BOM decoding failed, falling back to manual detection")

    # -------------------------------
    # Primary Encoding Attempt (UTF-8)
    # -------------------------------

    try:
        logger.info("Attempting UTF-8 decoding")
        text = raw_bytes.decode("utf-8")
        return _normalize_text(text)
    except UnicodeDecodeError:
        logger.warning("UTF-8 decoding failed")

    # -------------------------------
    # Secondary Attempt (UTF-16)
    # -------------------------------

    try:
        logger.info("Attempting UTF-16 decoding")
        text = raw_bytes.decode("utf-16")
        return _normalize_text(text)
    except UnicodeDecodeError:
        logger.warning("UTF-16 decoding failed")

    # -------------------------------
    # Regional Encoding Fallbacks
    # -------------------------------

    for encoding in FALLBACK_ENCODINGS:
        try:
            logger.info(f"Attempting fallback decoding: {encoding}")
            text = raw_bytes.decode(encoding)
            return _normalize_text(text)
        except UnicodeDecodeError:
            logger.warning(f"Fallback decoding failed: {encoding}")

    # -------------------------------
    # Final Failure
    # -------------------------------

    logger.error("All decoding attempts failed")

    raise ValueError(
        "Unable to decode subtitle file. File may be corrupted or not a text-based subtitle format."
    )


# ----------------------------------
# Internal Helpers
# ----------------------------------

def _detect_bom(raw_bytes: bytes) -> Optional[str]:
    """
    Detects BOM markers and returns matching Python encoding name.

    Returns:
        Encoding string or None
    """

    if raw_bytes.startswith(BOM_UTF8):
        return "utf-8-sig"

    if raw_bytes.startswith(BOM_UTF16_LE):
        return "utf-16-le"

    if raw_bytes.startswith(BOM_UTF16_BE):
        return "utf-16-be"

    return None


def _normalize_text(text: str) -> str:
    """
    Normalizes subtitle text for downstream processing.

    Operations:
    - Normalize line endings to Unix format
    - Remove zero-width characters
    - Strip BOM remnants
    """

    logger.debug("Normalizing decoded subtitle text")

    # Normalize Windows and legacy Mac line endings
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove zero-width space and BOM leftovers
    normalized = normalized.replace("\ufeff", "").replace("\u200b", "")

    return normalized.strip()
