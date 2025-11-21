import json
import re
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .limits import is_external_lookup_limit_exceeded, increment_external_lookup_count

# Загрузка БД ингредиентов
INGREDIENTS_DB_PATH = Path(__file__).parent.parent / "data" / "ingredients_db.json"
with open(INGREDIENTS_DB_PATH, encoding="utf-8") as f:
    INGREDIENTS_DB = json.load(f)

def normalize_ingredient(name: str) -> str:
    """Приводит название к ключу в БД: SODIUM_LAURETH_SULFATE"""
    name = re.sub(r"[^\w\s]", "", name).upper().replace(" ", "_")
    return name

def save_ingredients_db(db: dict):
    """Сохраняет базу данных ингредиентов."""
    with open(INGREDIENTS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def fetch_ingredient_from_external(ingredient_name: str, user_id: int) -> Optional[dict]:
    """Парсит информацию об ингредиенте из внешнего источника (INCI decoder)."""
    if is_external_lookup_limit_exceeded(user_id):
        return None

    # Пример: использовать сайт типа inci-decoder.com или подобный
    # Для демо используем фиктивный URL и парсинг
    url = f"https://incidecoder.com/ingredient/{ingredient_name.replace('_', '-').lower()}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Простой парсинг - извлекаем название и описание
            name = soup.find('h1').text if soup.find('h1') else ingredient_name
            description = soup.find('div', class_='description').text if soup.find('div', class_='description') else "No description"
            # Простая оценка риска на основе ключевых слов
            risk_level = "low"
            if any(word in description.lower() for word in ["irritant", "allergen", "toxic"]):
                risk_level = "high"
            data = {
                "name_ru": name,  # Assume English, but can add translation
                "risk_level": risk_level,
                "notes": description[:200],  # Limit length
                "bad_for": ["чувствительная кожа"] if risk_level == "high" else []
            }
            increment_external_lookup_count(user_id)
            return data
    except Exception as e:
        logging.error(f"Error fetching ingredient {ingredient_name}: {e}")
    return None

def parse_ingredients(raw: str) -> list:
    """Парсит INCI: разделение по ; или , и очистка"""
    # Убираем "Ingredients:", "ING:", "Aqua (Water)" и т.п.
    raw = re.sub(r"(?i)(ingredients?|ing|состав|состав\s*:\s*)[:\-]?", "", raw)
    parts = re.split(r"[,;]+", raw)
    return [normalize_ingredient(p.strip()) for p in parts if p.strip()]

def analyze_composition(ingredients: list, goal: str, category: str, subtype: str) -> dict:
    good, risky, bad = [], [], []
    goal_lower = goal.lower()

    for ing in ingredients:
        if ing in INGREDIENTS_DB:
            data = INGREDIENTS_DB[ing]
            name_ru = data["name_ru"]
            risk = data["risk_level"]

            # Простая логика (замените на продвинутую!)
            if risk == "low":
                good.append((ing, name_ru, data["notes"]))
            elif risk == "high" and any(trigger in goal_lower for trigger in ["чувствительная", "аллергия", "атопичная", "сухая", "повреждённая"]):
                if any(trigger in data["bad_for"] for trigger in ["чувствительная кожа", "сухие волосы", "повреждённые волосы"]):
                    bad.append((ing, name_ru, data["notes"]))
                else:
                    risky.append((ing, name_ru, data["notes"]))
            else:
                risky.append((ing, name_ru, data["notes"]))
        else:
            # Неизвестный компонент
            risky.append((ing, f"{ing} (неизвестно)", "Нет данных в базе"))

    score = max(3, 10 - len(bad) * 2 - len(risky) // 2)
    score = min(10, score)

    return {
        "good": good,
        "risky": risky,
        "bad": bad,
        "score": score,
        "recommendations": [
            "Обращайте внимание на первые 5 компонентов — они составляют основу средства.",
            "Для вашей цели важнее функциональные ингредиенты (увлажнители, кератин, церамиды), а не наполнители.",
            "Если в составе есть спирты (Alcohol Denat., Ethanol) — проверяйте их позицию: после 5-го места — обычно безопасно."
        ]
    }