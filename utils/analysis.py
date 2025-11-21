import json
import re
from pathlib import Path

# Загрузка БД ингредиентов
INGREDIENTS_DB_PATH = Path(__file__).parent.parent / "data" / "ingredients_db.json"
with open(INGREDIENTS_DB_PATH, encoding="utf-8") as f:
    INGREDIENTS_DB = json.load(f)

def normalize_ingredient(name: str) -> str:
    """Приводит название к ключу в БД: SODIUM_LAURETH_SULFATE"""
    name = re.sub(r"[^\w\s]", "", name).upper().replace(" ", "_")
    return name

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