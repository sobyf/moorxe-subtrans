import os
import json
import re
from datetime import datetime

STORAGE_DIR = os.path.join(os.getcwd(), "storage")

def save_fireworks_translation_data(filename: str, data: dict):
    try:
        clean_name = filename.lower().replace(".srt", "")
        clean_name = re.sub(r'[\s_]+', '-', clean_name)
        clean_name = re.sub(r'[^\w\-]', '', clean_name)

        movie_folder = os.path.join(STORAGE_DIR, clean_name)
        if not os.path.exists(movie_folder):
            os.makedirs(movie_folder)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"{clean_name}-{timestamp}.json"

        file_path = os.path.join(movie_folder, final_filename)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return file_path

    except Exception as e:
        return None