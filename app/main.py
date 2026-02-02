from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from app.utils.logger import setup_logger
from app.utils.decoder import decode_subtitle_bytes
from app.utils.parser import parse_srt_content
from app.utils.timeline import normalize_subtitle_timeline
from app.utils.cleaner import clean_subtitle_blocks

logger = setup_logger("srt-app")
MAX_FILE_SIZE = 5 * 1024 * 1024

app = FastAPI(title="SRT Translator", version="1.4.0")


class TranslationPreview(BaseModel):
    index: int
    timestamp: str
    original: str


class TranslationResponse(BaseModel):
    filename: str
    total_lines: int
    results: List[TranslationPreview]


@app.post("/translate-srt", response_model=TranslationResponse)
async def translate_srt(
        file: UploadFile = File(...),
        preview_limit: int = Query(20),
):
    if not file.filename.lower().endswith(".srt"):
        raise HTTPException(status_code=415, detail="Only .srt allowed.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        decoded_text = decode_subtitle_bytes(content)
        parsed_blocks = parse_srt_content(decoded_text)
        normalized_blocks = normalize_subtitle_timeline(parsed_blocks)
        cleaned_blocks = clean_subtitle_blocks(normalized_blocks)

        processing_slice = cleaned_blocks[:preview_limit]

        formatted_results = [
            TranslationPreview(
                index=block.get("index", i),
                timestamp=block.get("timestamp", ""),
                original=block.get("text", ""),
            )
            for i, block in enumerate(processing_slice)
        ]

        return TranslationResponse(
            filename=file.filename,
            total_lines=len(formatted_results),
            results=formatted_results
        )

    except Exception as e:
        logger.error(f"Failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")