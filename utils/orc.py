import io
import re
from PIL import Image
import pytesseract
import logging

logger = logging.getLogger(__name__)

def extract_text_from_photo(photo_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(photo_bytes))
        # Конвертируем в grayscale для улучшения OCR
        image = image.convert('L')
        text = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
        # Очистка: оставляем только латинские буквы, цифры, запятые, точки с запятой, скобки
        cleaned = re.sub(r'[^a-zA-Z0-9\(\),;\-\s]', '', text)
        return cleaned.strip()
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""