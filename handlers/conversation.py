from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import logging
from utils.limits import is_limit_exceeded, increment_count
from utils.orc import extract_text_from_photo
from utils.analysis import parse_ingredients, analyze_composition
from config import ADMIN_USERNAME

logger = logging.getLogger(__name__)

# Состояния
(
    SELECT_CATEGORY,
    SELECT_SUBTYPE,
    SELECT_GOAL,
    UPLOAD_INGREDIENTS,
) = range(4)

def make_contact_button(text: str) -> InlineKeyboardButton:
    url = f"tg://resolve?domain={ADMIN_USERNAME}&text={text.replace(' ', '%20')}"
    return InlineKeyboardButton(text, url=url)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_limit_exceeded(user_id):
        await update.message.reply_text(
            "🚫 Вы использовали все 5 бесплатных запросов на сегодня.\n\n"
            "💡 Хотите безлимитный доступ и персональные рекомендации?",
            reply_markup=InlineKeyboardMarkup([[
                make_contact_button("Купить подписку на бот")
            ]])
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🧴 Уход за кожей", callback_data="cat:skin")],
        [InlineKeyboardButton("💇 Уход за волосами", callback_data="cat:hair")],
    ]
    await update.message.reply_text(
        "✨ Привет! Я — бот-косметолог 🧪\n"
        "Я помогу разобрать состав любого средства и сказать: подходит ли оно вам.\n\n"
        "👉 Сначала выберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_CATEGORY

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":")[1]
    context.user_data["category"] = category

    if category == "skin":
        subtypes = ["Лицо", "Тело", "Руки/Ноги"]
    else:
        subtypes = ["Шампунь", "Бальзам/Кондиционер", "Маска", "Спрей/Сыворотка", "Укладка"]

    keyboard = [[
        InlineKeyboardButton(st, callback_data=f"sub:{st}")
        for st in subtypes[i:i+2]
    ] for i in range(0, len(subtypes), 2)]

    await query.edit_message_text(
        "🎯 Отлично! Теперь уточните тип средства:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SUBTYPE

async def subtype_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    subtype = query.data.split(":")[1]
    context.user_data["subtype"] = subtype

    examples = {
        "Лицо": "увлажнить, снять покраснение, бороться с морщинами",
        "Руки/Ноги": "смягчить грубую кожу, убрать трещины на пятках",
        "Шампунь": "очистить жирную кожу головы, уменьшить зуд",
        "Маска": "восстановить сильно повреждённые волосы, увлажнить сухие кончики"
    }
    hint = examples.get(subtype, "например: увлажнить, укрепить, смягчить, защитить")

    await query.edit_message_text(
        f"💬 Какую проблему вы хотите решить с помощью этого средства?\n\n"
        f"Примеры для «{subtype}»:\n• {hint}\n\n"
        "Напишите кратко (1–2 предложения):"
    )
    return SELECT_GOAL

async def goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal = update.message.text.strip()
    if not goal:
        await update.message.reply_text("❌ Пожалуйста, опишите цель (например: *«увлажнить сухую кожу лица»*).", parse_mode=ParseMode.MARKDOWN)
        return SELECT_GOAL

    context.user_data["goal"] = goal

    await update.message.reply_text(
        "📸 Теперь отправьте:\n"
        "• Фото этикетки (чётко, без бликов), ИЛИ\n"
        "• Текст состава (латиницей, как на упаковке)\n\n"
        "Например: *Aqua, Glycerin, Panthenol, Sodium Laureth Sulfate...*",
        parse_mode=ParseMode.MARKDOWN
    )
    return UPLOAD_INGREDIENTS

async def ingredients_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_ingredients = ""

    # Получаем текст или фото
    if update.message.photo:
        photo = update.message.photo[-1]  # самый большой
        file = await photo.get_file()
        photo_bytes = await file.download_as_bytearray()
        raw_ingredients = extract_text_from_photo(bytes(photo_bytes))
        if not raw_ingredients:
            await update.message.reply_text(
                "❌ Не удалось распознать текст на фото.\n\n"
                "Пожалуйста, отправьте состав текстом (латиницей, через запятую или точку с запятой)."
            )
            return UPLOAD_INGREDIENTS
    elif update.message.text:
        raw_ingredients = update.message.text.strip()
    else:
        await update.message.reply_text("❗ Отправьте фото или текст.")
        return UPLOAD_INGREDIENTS

    # Парсим состав
    ingredients = parse_ingredients(raw_ingredients)
    if not ingredients:
        await update.message.reply_text(
            "❌ Не удалось распознать компоненты. Убедитесь, что текст на латинице и содержит названия вроде *Glycerin*, *Panthenol*.\n\n"
            "Попробуйте ещё раз:"
        )
        return UPLOAD_INGREDIENTS

    # Сохраняем
    context.user_data["ingredients_raw"] = raw_ingredients
    context.user_data["ingredients_parsed"] = ingredients

    # Анализ
    category = context.user_data["category"]
    subtype = context.user_data["subtype"]
    goal = context.user_data["goal"]

    report = analyze_composition(ingredients, goal, category, subtype)

    # Формируем ответ
    lines = [
        f"🧴 *Анализ состава: {subtype}*\n",
        f"🎯 *Ваша цель:* {goal}\n",
    ]

    if report["good"]:
        lines.append("✅ *Подходящие компоненты:*")
        for key, name, note in report["good"][:5]:
            lines.append(f"• *{name}* — {note}")
        if len(report["good"]) > 5:
            lines.append(f"... и ещё {len(report['good']) - 5}")

    if report["risky"]:
        lines.append("\n⚠️ *Спорные / требуют осторожности:*")
        for key, name, note in report["risky"][:5]:
            lines.append(f"• *{name}* — {note}")

    if report["bad"]:
        lines.append("\n❌ *Нежелательные для вашей цели:*")
        for key, name, note in report["bad"][:5]:
            lines.append(f"• *{name}* — {note}")

    lines.append(f"\n📊 *Общая оценка:* {report['score']}/10")
    lines.append("\n💡 *Рекомендации:*")
    for rec in report["recommendations"]:
        lines.append(f"• {rec}")

    lines.append(
        "\n⚠️ *Важно:* Бот не заменяет консультацию дерматолога или трихолога.\n\n"
        "Хотите *персональный разбор ухода за волосами* от профессионалов?"
    )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [make_contact_button("Хочу разбор ухода")],
            [InlineKeyboardButton("🔄 Заново", callback_data="restart")]
        ])
    )

    # Увеличиваем счётчик
    increment_count(user_id)

    return ConversationHandler.END

async def cancel_or_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "restart":
        return await start_handler(query, context)
    return ConversationHandler.END