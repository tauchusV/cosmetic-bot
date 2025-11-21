import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.conversation import (
    start_handler, category_handler, subtype_handler,
    goal_handler, ingredients_handler, cancel_or_restart, lift_limit_handler,
    SELECT_CATEGORY, SELECT_SUBTYPE, SELECT_GOAL, UPLOAD_INGREDIENTS
)
from telegram.ext import ConversationHandler

# Логгирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(category_handler, pattern=r"^cat:")],
            SELECT_SUBTYPE: [CallbackQueryHandler(subtype_handler, pattern=r"^sub:")],
            SELECT_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_handler)],
            UPLOAD_INGREDIENTS: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, ingredients_handler)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_or_restart, pattern=r"^restart$")
        ],
        per_chat=True,
        per_user=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(cancel_or_restart, pattern=r"^restart$"))
    application.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(
        "📌 Как пользоваться:\n"
        "1. Нажмите /start\n"
        "2. Выберите категорию и тип средства\n"
        "3. Опишите цель\n"
        "4. Отправьте состав (текст или фото)\n"
        "5. Получите анализ!\n\n"
        "Лимит: 5 бесплатных запросов в сутки."
    )))
    application.add_handler(CommandHandler("lift", lift_limit_handler))

    print("✅ Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()