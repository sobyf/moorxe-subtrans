import math
import json
from typing import List , Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from app.utils.logger import setup_logger
from app.utils.decoder import decode_subtitle_bytes
from app.utils.parser import parse_srt_content
from app.utils.timeline import normalize_subtitle_timeline
from app.utils.cleaner import prepare_for_translation
from app.services.fireworks import translate_chunk
from app.utils.storage import save_fireworks_translation_data
import re
import os

logger = setup_logger("srt-app")
MAX_FILE_SIZE = 5 * 1024 * 1024

app = FastAPI(title="SRT Translator", version="1.4.0")

BASE_STORAGE = os.path.join(os.getcwd(), "storage")
SRT_OUTPUT_DIR = os.path.join(BASE_STORAGE, "srt")


class TranslationPreview(BaseModel):
    index: int
    timestamp: str
    original: str


class Chunk(BaseModel):
    chunk_id: int
    range: str
    estimated_tokens: int
    data: List[TranslationPreview]


class TranslationResponse(BaseModel):
    filename: str
    total_lines: int
    total_chunks: int
    total_tokens: int
    results: List[Chunk]

class TestRequest(BaseModel):
    title: str = "The Dark Knight"
    genre: str = "Action/Crime"
    extra_context: str = "Street slang and aggressive tone"
    data: List[Dict] # لیست آبجکت‌ها شامل index و original


def estimate_json_tokens(obj: any) -> int:
    """
    Estimates tokens for the entire JSON structure.
    Gemini uses about 1 token per 4 characters for English/JSON.
    """
    json_string = json.dumps(obj)
    # Average: 4 chars per token + safety margin
    return math.ceil(len(json_string) / 3.8)


@app.post("/translate")
async def translate_srt(
        file: UploadFile = File(...),
        chunk_size: int = Query(30, ge=10, le=200),
        genre: str = Query("General"),
        extra_context: str = Query(None)
):
    if not file.filename.lower().endswith(".srt"):
        raise HTTPException(status_code=415, detail="Only .srt files are allowed.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    extracted_title = os.path.splitext(file.filename)[0]

    try:
        # آماده‌سازی اولیه
        decoded_text = decode_subtitle_bytes(content)
        parsed_blocks = parse_srt_content(decoded_text)
        normalized_blocks = normalize_subtitle_timeline(parsed_blocks)
        final_blocks = prepare_for_translation(normalized_blocks)

        all_translated_items = []
        total_chunks = (len(final_blocks) + chunk_size - 1) // chunk_size

        # پاکسازی نام فیلم برای استفاده در مسیرها
        clean_title = re.sub(r'[^\w\-]', '', extracted_title.lower().replace(" ", "-"))

        # حلقه ترجمه
        for i in range(0, len(final_blocks), chunk_size):
            batch = final_blocks[i: i + chunk_size]
            current_chunk_data = [{"index": b["index"], "original": b["text"]} for b in batch]

            # ارسال به سرویس Fireworks
            translated_batch = await translate_chunk(
                chunk_data=current_chunk_data,
                title=clean_title,
                genre=genre,
                extra_context=extra_context
            )
            all_translated_items.extend(translated_batch)
            logger.info(f"[{extracted_title}] Processed chunk {i // chunk_size + 1}/{total_chunks}")

        # ذخیره دیتای خام Fireworks (بک‌آپ)
        foreworks_data = {
            "status": "success",
            "metadata": {"title": clean_title, "genre": genre},
            "translated_data": all_translated_items
        }
        # استفاده از clean_title برای نام فایل JSON
        save_fireworks_translation_data(f"{clean_title}.json", foreworks_data)

        # نقشه نگاشت ایندکس به متن ترجمه شده
        # نقشه نگاشت ایندکس به متن ترجمه شده
        trans_map = {str(item["index"]): item["translated"] for item in all_translated_items}
        # RLM = "\u200f"
        # بازسازی رشته SRT
        # تنظیم متن امضا
        signature_text = "{\\an8}Localized by AI Architecture"

        srt_final_string = ""
        current_idx = 1  # شمارنده هوشمند برای مدیریت ترتیب ایندکس‌ها

        # ۱. اضافه کردن امضا به ابتدای فیلم (ثانیه ۱ تا ۵)
        srt_final_string += f"{current_idx}\n00:00:01,000 --> 00:00:05,000\n{signature_text}\n\n"
        current_idx += 1

        # ۲. ساخت بدنه اصلی زیرنویس
        for block in normalized_blocks:
            idx_str = str(block["index"])
            translated_text = trans_map.get(idx_str, "").strip()

            # حذف کاراکترهای کنترلی برای جلوگیری از نمایش "مربع" در پلیرهای قدیمی
            translated_text = translated_text.replace('\u200f', '').replace('\u200e', '')

            # منطق انتخاب متن
            if translated_text:
                final_text = translated_text
            elif "[" in block["text"] or "]" in block["text"] or "♪" in block["text"]:
                final_text = ""
            else:
                final_text = block["text"]

            # ساخت بلاک SRT با ایندکس جدید
            # اگر نمی‌خواهی خطوط خالی در فایل باشند، شرط if final_text: را بگذار
            srt_final_string += f"{current_idx}\n"
            srt_final_string += f"{block['start']} --> {block['end']}\n"
            srt_final_string += f"{final_text}\n\n"

            current_idx += 1

        # ۳. اضافه کردن امضا به انتهای فیلم
        if normalized_blocks:
            # گرفتن زمان پایان آخرین دیالوگ برای شروع امضای آخر
            last_end_time = normalized_blocks[-1]['end']
            # نمایش امضا برای ۵ ثانیه بعد از آخرین دیالوگ (تخمینی)
            srt_final_string += f"{current_idx}\n{last_end_time} --> 99:00:00.000\n{signature_text}\n\n"

        # ۴. ایجاد پوشه و ذخیره‌سازی نهایی با فرمت استاندارد BOM
        movie_folder = os.path.join(SRT_OUTPUT_DIR, clean_title)
        os.makedirs(movie_folder, exist_ok=True)

        final_path = os.path.join(movie_folder, f"{clean_title}-persian.srt")
        with open(final_path, "w", encoding="utf-8-sig") as f:
            f.write(srt_final_string)

        return {
            "status": "success",
            "message": "Translation completed and file saved.",
            "file_info": {
                "title": clean_title,
                "path": final_path,
                "total_lines": len(normalized_blocks)
            }
        }

    except Exception as e:
        file_name = file.filename if file else "Unknown File"
        logger.error(f"Pipeline Failure for {file_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test")
async def test_fireworks_logic(request: TestRequest):
    try:
        logger.info(f"Testing Fireworks with: {request.title}")

        # ۱. ارسال دیتا به موتور ترجمه (Fireworks)
        results = await translate_chunk(
            chunk_data=request.data,
            title=request.title,
            genre=request.genre,
            extra_context=request.extra_context
        )

        # ۲. آماده‌سازی دیتای نهایی برای خروجی و ذخیره سازی
        final_response = {
            "status": "success",
            "engine": "Fireworks-DeepSeek-V3",
            "metadata": {
                "title": request.title,
                "genre": request.genre,
                "extra_context": request.extra_context
            },
            "translated_data": results
        }

        # ۳. ذخیره فیزیکی دیتا در پوشه storage

        return final_response

    except Exception as e:
        logger.error(f"Fireworks Test Route Failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


