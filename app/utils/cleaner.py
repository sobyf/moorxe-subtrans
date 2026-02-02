# app/utils/cleaner.py

import re
from app.utils.logger import setup_logger

logger = setup_logger("srt-cleaner")

# -------------------------------------------------
# LOW LEVEL CLEANING PATTERNS
# -------------------------------------------------

CONTROL_CHARS_PATTERN = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]"
)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")

# Subtitle noise
MUSIC_PATTERN = re.compile(r"[♪♫].*?[♪♫]")
BRACKET_EFFECT_PATTERN = re.compile(r"[\[\(].*?[\]\)]")
SPEAKER_PREFIX_PATTERN = re.compile(r"^[A-Z][A-Z0-9_ ]{1,20}:\s+")

DIALOG_PREFIX_PATTERN = re.compile(r"^[-–—]+\s*")
STUTTER_REPEAT_PATTERN = re.compile(r"\b(\w+(?:'\w+)?)--\s*\1\b", re.IGNORECASE)
BROKEN_STUTTER_PATTERN = re.compile(r"\b([A-Za-z])-\1([A-Za-z]+)", re.IGNORECASE)
MID_DASH_PATTERN = re.compile(r"\s*--+\s*")

# Sentence detection
SENTENCE_END_PATTERN = re.compile(r"[.!?]$")

# -------------------------------------------------
# BASIC TEXT NORMALIZATION
# -------------------------------------------------

def _normalize_text(text: str) -> str:
    text = CONTROL_CHARS_PATTERN.sub("", text)
    text = HTML_TAG_PATTERN.sub("", text)
    text = MUSIC_PATTERN.sub("", text)
    text = BRACKET_EFFECT_PATTERN.sub("", text)
    text = SPEAKER_PREFIX_PATTERN.sub("", text)
    text = DIALOG_PREFIX_PATTERN.sub("", text)

    text = STUTTER_REPEAT_PATTERN.sub(r"\1", text)
    text = BROKEN_STUTTER_PATTERN.sub(r"\1\2", text)
    text = MID_DASH_PATTERN.sub(" ", text)

    text = WHITESPACE_PATTERN.sub(" ", text)

    return text.strip()



# -------------------------------------------------
# ENGLISH TRANSLATION CONDITIONING
# -------------------------------------------------

CONTRACTIONS = {
    "I'm": "I am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "it's": "it is",
    "don't": "do not",
    "doesn't": "does not",
    "can't": "cannot",
    "won't": "will not",
    "ain't": "is not",
    "gonna": "going to",
    "wanna": "want to",
    "gotta": "got to",
    "lemme": "let me"
}


def _expand_contractions(text: str) -> str:
    for k, v in CONTRACTIONS.items():
        text = re.sub(rf"\b{k}\b", v, text, flags=re.IGNORECASE)
    return text


def _normalize_casing(text: str) -> str:
    if text.isupper():
        return text.capitalize()
    return text


# -------------------------------------------------
# PUBLIC CLEANING API
# -------------------------------------------------

def clean_subtitle_text(text: str) -> str:
    """
    High quality subtitle normalization for MT input
    """

    cleaned = _normalize_text(text)
    cleaned = _expand_contractions(cleaned)
    cleaned = _normalize_casing(cleaned)

    return cleaned


def clean_subtitle_blocks(blocks: list[dict]) -> list[dict]:
    logger.info(f"Normalizing {len(blocks)} subtitle blocks")

    output = []

    for block in blocks:
        text = clean_subtitle_text(block["text"])

        new_block = block.copy()
        new_block["text"] = text
        output.append(new_block)

    return output


# -------------------------------------------------
# SENTENCE RECONSTRUCTION ENGINE
# -------------------------------------------------

def reconstruct_sentences(
    blocks: list[dict],
    max_gap_ms: int = 700,
    min_merge_chars: int = 45
) -> list[dict]:
    """
    Merges fragmented subtitle lines into full sentences
    """

    logger.info("Reconstructing sentence fragments")

    merged = []
    buffer = None

    for block in blocks:

        if buffer is None:
            buffer = block.copy()
            continue

        prev_end = buffer["end"]
        curr_start = block["start"]

        gap = curr_start - prev_end

        should_merge = (
            gap <= max_gap_ms and
            len(buffer["text"]) < min_merge_chars and
            not SENTENCE_END_PATTERN.search(buffer["text"])
        )

        if should_merge:
            buffer["text"] += " " + block["text"]
            buffer["end"] = block["end"]
        else:
            merged.append(buffer)
            buffer = block.copy()

    if buffer:
        merged.append(buffer)

    logger.info(f"Sentence merge result: {len(merged)} blocks")

    return merged


# -------------------------------------------------
# TRANSLATION CHUNK PACKAGING
# -------------------------------------------------

def prepare_translation_chunks(
    blocks: list[dict],
    max_chars: int = 450
) -> list[dict]:
    """
    Produces translation-safe chunks for NLLB
    """

    logger.info("Preparing translation chunks")

    chunks = []

    for block in blocks:

        text = block["text"]

        if len(text) <= max_chars:
            chunks.append(block)
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text)

        buffer = ""

        for sentence in sentences:

            if len(buffer) + len(sentence) <= max_chars:
                buffer += " " + sentence if buffer else sentence
            else:
                chunk = block.copy()
                chunk["text"] = buffer.strip()
                chunks.append(chunk)
                buffer = sentence

        if buffer:
            chunk = block.copy()
            chunk["text"] = buffer.strip()
            chunks.append(chunk)

    logger.info(f"Generated {len(chunks)} translation chunks")

    return chunks


# -------------------------------------------------
# FULL PIPELINE ENTRYPOINT
# -------------------------------------------------

def prepare_for_translation(blocks: list[dict]) -> list[dict]:
    """
    Complete Phase A pipeline:
    Clean → Reconstruct → Chunk
    """

    cleaned = clean_subtitle_blocks(blocks)
    reconstructed = reconstruct_sentences(cleaned)
    final_chunks = prepare_translation_chunks(reconstructed)

    return final_chunks


# دستورالعمل طلایی ما که حالا بخشی از User Prompt است
instructions = (
    "نقش: بازنویس زیرنویس سینمایی.\n"
    "وظیفه: تبدیل فارسی رسمی به محاوره‌ای با قوانین زیر:\n"
    "- افعال شکسته و اتصال گفتاری استفاده کن.\n"
    "- معنا، زمان فعل، شخص و جهت سوال حفظ شود (چطور ≠ چرا).\n"
    "- استعاره‌ها جایگزین شوند («چشم‌ها همه جا هستند» → «تحت نظرم»).\n"
    "- مجهول رسمی به محاوره‌ای تبدیل شود («تماشا می‌شوم» → «تحت نظرم»).\n"
    "- در واکنش‌ها از «شد» استفاده کن («خوب شد زنگ زدی»).\n"
    "- افعال ذهنی ساده باشند؛ «دارن + فعل» فقط برای کنش واقعی.\n"
    "- فعل ربطی کوتاه شود («هستم» → «م»).\n"
    "- گزاره‌های واقعی دقیق حفظ شوند.\n"
    "- فقط متن بازنویسی شده را برگردان، بدون هیچ توضیح اضافه."
)

f"{instructions}\n\n"
