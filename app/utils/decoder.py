from typing import Optional
from app.utils.logger import setup_logger

logger = setup_logger("srt-decoder")

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"
FALLBACK_ENCODINGS = ("windows-1256", "windows-1252", "iso-8859-1")

def decode_subtitle_bytes(raw_bytes: bytes) -> str:
    if not raw_bytes:
        raise ValueError("File is empty")

    encoding_hint = _detect_bom(raw_bytes)
    if encoding_hint:
        try:
            return _normalize_text(raw_bytes.decode(encoding_hint))
        except UnicodeDecodeError:
            pass

    for enc in ("utf-8", "utf-16") + FALLBACK_ENCODINGS:
        try:
            return _normalize_text(raw_bytes.decode(enc))
        except UnicodeDecodeError:
            continue

    raise ValueError("Unable to decode subtitle file.")

def _detect_bom(raw_bytes: bytes) -> Optional[str]:
    if raw_bytes.startswith(BOM_UTF8): return "utf-8-sig"
    if raw_bytes.startswith(BOM_UTF16_LE): return "utf-16-le"
    if raw_bytes.startswith(BOM_UTF16_BE): return "utf-16-be"
    return None

def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\ufeff", "").replace("\u200b", "").strip()