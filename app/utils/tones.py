import re

GENRE_TONES = {
    "Action": "Energetic, street-smart, punchy",
    "Adventure": "Energetic and heroic",
    "Animation": "Clear, playful, slightly exaggerated",
    "Biography": "Natural and respectful",
    "Comedy": "Playful, witty, casual",
    "Crime": "Gritty, street-smart, tough",
    "Drama": "Emotional, natural, sincere",
    "Family": "Warm, simple, friendly",
    "Fantasy": "Epic, expressive, imaginative",
    "Film-Noir": "Dark, sharp, cynical",
    "History": "Serious and respectful",
    "Horror": "Dark, tense, suspenseful",
    "Music": "Rhythmic and expressive",
    "Musical": "Expressive and emotional",
    "Mystery": "Calm, tense, subtle",
    "Romance": "Soft, intimate, emotional",
    "Sci-Fi": "Modern, natural, slightly technical",
    "Sport": "Energetic and motivational",
    "Thriller": "Tense, sharp, fast-paced",
    "War": "Serious, heavy, intense",
    "Western": "Rugged, tough, slightly dramatic",
    "Reality-TV": "Casual and natural",
    "Documentary": "Natural, clear, slightly formal",
    "Talk-Show": "Casual and conversational",
    "Game-Show": "Fun and energetic",
    "News": "Natural, clear, slightly formal",
    "General": "Natural and everyday"
}


def get_genre_prompt(genre_string: str) -> str:
    # ۱. جدا کردن ژانرها بر اساس ویرگول یا اسلش و تمیز کردن فاصله‌ها
    # مثال: "Action / Drama" تبدیل می‌شود به ["Action", "Drama"]
    genres = [g.strip() for g in re.split(r'[,/]', genre_string) if g.strip()]

    combined_tones = []

    for g in genres:
        # پیدا کردن لحن هر ژانر؛ اگر وجود نداشت نادیده گرفتن آن
        tone = GENRE_TONES.get(g)
        if tone and tone not in combined_tones:
            combined_tones.append(tone)

    # ۲. اگر هیچ ژانر معتبری پیدا نشد، از General استفاده کن
    if not combined_tones:
        return f"Tone: {GENRE_TONES['General']}"

    # ۳. ترکیب تمام لحن‌ها با ویرگول برای ساخت یک پرامپت واحد
    return f"Tone: {', '.join(combined_tones)}"