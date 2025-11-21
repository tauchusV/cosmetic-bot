import json

# Имена файлов частей (сохраните каждую часть как .json)
PARTS = [
    "part1.json",
    "part2.json",
    "part3.json",
    "part4.json",
    "part5.json",
    "part6.json"
]

full_db = {}

for part_file in PARTS:
    with open(part_file, "r", encoding="utf-8") as f:
        part_data = json.load(f)
        # Убираем дубли (если были для надёжности)
        for key, value in part_data.items():
            if key not in full_db:  # берём первое вхождение
                full_db[key] = value

print(f"✅ Собрано {len(full_db)} уникальных ингредиентов.")

# Сохраняем
with open("ingredients_db.json", "w", encoding="utf-8") as f:
    json.dump(full_db, f, ensure_ascii=False, indent=2)

print("📁 Файл сохранён: ingredients_db.json")