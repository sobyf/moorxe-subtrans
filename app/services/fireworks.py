import os
import json
import asyncio
import re
from typing import List, Dict, Any, cast , Iterable , cast
from openai import AsyncOpenAI
from groq import AsyncGroq
from dotenv import load_dotenv
from app.utils.logger import setup_logger
from app.utils.tones import get_genre_prompt
from groq.types.chat import ChatCompletionMessageParam
load_dotenv()
logger = setup_logger("Ai-Translation")


# client = AsyncGroq(
#     api_key=os.getenv("GROQ_AI_API_KEY"),
# )

# مدل پیشنهادی برای Groq (با توجه به تست‌های قبلی)
# MODEL_NAME = "meta-llama/llama-4-maverick-17b-128e-instruct"

# open ai
client = AsyncOpenAI(
    api_key=os.getenv("GITHUB_API_KEY"),
    base_url="https://models.github.ai/inference",
)
MODEL_NAME = "openai/gpt-5-nano"

SYSTEM_PROMPT = (
    "You are a top-tier Persian subtitle translator for Iranian movie audiences.\n"

    "TRANSLATION APPROACH:\n"
    "• Translate into natural, authentic, modern spoken Iranian Persian (Tehrani colloquial style – 2020s)\n"
    "• Turn idioms, slang, metaphors, sarcasm, humor into the most natural Persian equivalents – NEVER translate literally\n"
    "• Preserve ORIGINAL MEANING and emotional tone exactly\n"
    "• Keep translations concise - match subtitle timing\n\n"

    "CRITICAL RULES:\n"
    "1. Output ONLY Persian script (no Latin/Cyrillic letters)\n"
    "2. Use colloquial Persian forms\n"
    "3. Preserve irony/sarcasm - don't make it literal\n"
    "4. Use MODERN vocabulary (2020s Iranian speech)\n"
    "5. For names/proper nouns: Transliterate to Persian script—never translate meanings\n"
    "6. Keep character/term consistency across the movie\n"
    "7. For ambiguous lines: Choose most context-appropriate natural Persian interpretation\n\n"

    "TECHNICAL REQUIREMENTS:\n"
    "• Return JSON with 'results' array containing 'index' and 'translated'\n"
    "• Use EXACT same index numbers from input (vital for SRT sync)\n"
    "• One translation per line - no merging/splitting\n"
    "• Array order doesn't matter - indexes handle mapping\n\n"

    "Example output format:\n"
    '{"results": [{"index": "1", "translated": "ترجمه فارسی"}]}'
)


semaphore = asyncio.Semaphore(1)

def safe_extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*|```$', '', text, flags=re.MULTILINE).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return ""


async def translate_chunk(
        chunk_data: List[Dict[str, Any]],
        title: str = "Unknown",
        genre: str = "General",
        extra_context: str = ""
) -> List[Dict[str, Any]]:
    async with semaphore:
        max_retries = 5
        retry_delay = 120  # 2 minutes break

        for attempt in range(max_retries + 1):
            try:
                # تغییر در نحوه ساخت payload برای حذف خطوط خالی قبل از ارسال به مدل
                payload = [
                    {"index": item["index"], "original": item["original"]}
                    for item in chunk_data
                    if item["original"].strip()  # فقط خطوطی که متن دارند را بفرست
                ]
                genre_tone = get_genre_prompt(genre)

                user_prompt = (
                    f"Title: {title}\n"
                    f"Primary Tone: {genre_tone}\n"
                    f"Genres: {genre}\n"
                    f"Scene Context: {extra_context if extra_context else 'N/A'}\n\n"
                    f"DATA TO TRANSLATE (JSON):\n{json.dumps(payload, ensure_ascii=False)}"
                )

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]


                # openai
                chat_completion = await client.chat.completions.create(
                    messages=cast(Any, messages),
                    model=MODEL_NAME,
                    temperature=0.1,
                    max_tokens=4096
                )

                # groq
                formatted_messages = cast(Iterable[ChatCompletionMessageParam], cast(Any, messages))
                # chat_completion = await client.chat.completions.create(
                #     messages=formatted_messages,
                #     model=MODEL_NAME,
                #     temperature=0.1 ,
                #     max_tokens=4096,
                #     response_format=cast(Any, {"type": "json_object"})
                # )

                raw_content = chat_completion.choices[0].message.content
                if not raw_content:
                    raise ValueError("Fireworks returned an empty response.")

                clean_json = safe_extract_json(raw_content)
                if not clean_json:
                    raise ValueError(f"No valid JSON object detected in response: {raw_content[:100]}...")

                parsed_response = json.loads(clean_json)

                # استخراج لیست نتایج
                raw_results = []
                if isinstance(parsed_response, list):
                    raw_results = parsed_response
                elif isinstance(parsed_response, dict):
                    if "results" in parsed_response:
                        raw_results = parsed_response["results"]
                    elif "translations" in parsed_response:
                        raw_results = parsed_response["translations"]
                    elif len(parsed_response) == 1:
                        raw_results = list(parsed_response.values())[0]

                # --- PROTECT AGAINST INVALID TYPE ---
                if not isinstance(raw_results, list):
                    logger.error(f"Type Mismatch: Expected list, got {type(raw_results).__name__} for {title}")
                    raise ValueError("Model returned invalid results structure")

                # --- GUARANTEED SYNC LOGIC ---
                expected_indices = {str(item["index"]) for item in chunk_data}
                received_indices = {str(item.get("index", "")) for item in raw_results}

                missing = expected_indices - received_indices
                if missing:
                    logger.warning(f"⚠️ Index mismatch for {title}. Missing: {missing}")
                # ------------------------------------

                # --- GUARANTEED SYNC LOGIC ---
                translation_map = {}
                for item in raw_results:
                    try:
                        idx = str(item.get("index", ""))
                        val = item.get("translated", "")
                        if idx and val:
                            translation_map[idx] = val
                    except (KeyError, TypeError, AttributeError):
                        continue

                final_sync_results: List[Dict[str, Any]] = []
                for original_item in chunk_data:
                    orig_idx = str(original_item["index"])
                    translated_text = translation_map.get(orig_idx, original_item["original"])

                    final_sync_results.append({
                        "index": original_item["index"],
                        "translated": translated_text
                    })

                return final_sync_results

            except Exception as e:
                error_str = str(e).lower()
                # بررسی محدودیت نرخ درخواست یا خطاهای مربوطه
                is_rate_limit = any(
                    x in error_str for x in ["rate limit", "429", "too many requests", "scraping github"])

                if is_rate_limit and attempt < max_retries:
                    logger.warning(
                        f"⚠️ Limit hit for {title}. Attempt {attempt + 1}/{max_retries}. Sleeping 2 minutes...")
                    await asyncio.sleep(retry_delay)
                    continue  # تکرار همین چانک از ابتدا

                # برای خطاهای غیر از لیمیت یا تمام شدن تلاش‌ها
                if attempt < max_retries:
                    logger.error(
                        f"⚠️ Unexpected error for {title}: {str(e)}. Attempt {attempt + 1}/{max_retries}. Retrying...")
                    await asyncio.sleep(10)
                    continue

                logger.error(f"Fireworks Sync Failure after {max_retries} retries: {str(e)}", exc_info=True)
                # بازگرداندن مقدار پیش‌فرض در صورت شکست نهایی
                return [{"index": item["index"], "translated": item.get("original", "Error")} for item in chunk_data]

            finally:
                # مکث ثابت بین هر چانک (موفق یا ناموفق)
                await asyncio.sleep(12)

        # مقدار بازگشتی نهایی برای آرام کردن تحلیل‌گر تایپ
        return [{"index": item["index"], "translated": item.get("original", "Error")} for item in chunk_data]