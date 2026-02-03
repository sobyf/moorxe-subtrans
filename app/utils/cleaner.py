import re
from app.utils.logger import setup_logger

logger = setup_logger("srt-cleaner")

PATTERNS = {
    "control": re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]"),
    "html": re.compile(r"<[^>]+>"),
    # نویزهایی مثل [Music] یا (Laughter)
    "noise": re.compile(r"[♪♫].*?[♪♫]|[\[\(].*?[\]\)]|^[A-Z][A-Z0-9_ ]{1,20}:\s+|^[-–—]+\s*"),
    "stutter": re.compile(r"\b(\w+)--\s*\1\b|\b([A-Za-z])-\2([A-Za-z]+)", re.IGNORECASE),
    "space": re.compile(r"\s+"),
    "sent_end": re.compile(r"[.!?]$")
}

CONTRACTIONS = {"I'm": "I am", "you're": "you are", "it's": "it is", "don't": "do not", "gonna": "going to",
                "wanna": "want to"}

def clean_subtitle_text(text: str) -> str:
    text = PATTERNS["control"].sub("", text)
    text = PATTERNS["html"].sub("", text)
    text = PATTERNS["noise"].sub("", text)
    text = PATTERNS["stutter"].sub(r"\1\2\3", text)

    for k, v in CONTRACTIONS.items():
        text = re.sub(rf"\b{k}\b", v, text, flags=re.IGNORECASE)

    if text.isupper(): text = text.capitalize()
    return PATTERNS["space"].sub(" ", text).strip()

def clean_subtitle_blocks(blocks: list[dict]) -> list[dict]:
    output = []
    for block in blocks:
        new_block = block.copy()
        # متن را تمیز می‌کنیم؛ اگر نویز بود، رشته خالی برمی‌گرداند
        new_block["text"] = clean_subtitle_text(block["text"])
        output.append(new_block)
    return output

def prepare_for_translation(blocks: list[dict]) -> list[dict]:
    """
    نسخه اصلاح شده: فقط پاکسازی انجام می‌دهد و ردیف‌ها را ادغام نمی‌کند
    تا ساختار ایندکس‌ها برای مدل Fireworks دست‌نخورده باقی بماند.
    """
    return clean_subtitle_blocks(blocks)




