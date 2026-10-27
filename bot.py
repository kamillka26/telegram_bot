import logging
import json
import datetime
import asyncio
from pathlib import Path

import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and
# POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

MOODS_FILE = Path("moods.json")


def load_moods() -> list:
    """Загружает историю настроений из файла."""
    if not MOODS_FILE.exists():
        return []
    try:
        with open(MOODS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_mood(user_id: int, score: int) -> None:
    """Сохраняет новую оценку настроения."""
    data = load_moods()
    data.append({
        "user_id": user_id,
        "date": datetime.datetime.now().isoformat(),
        "score": score,
    })
    with open(MOODS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# Define a few command handlers. These usually take the two arguments update
# and context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    text = (
        f"Привет, {user.mention_html()}! 🧘‍♂️\n\n"
        "Я помогу тебе позаботиться о ментальном здоровье.\n\n"
        "Доступные команды:\n"
        "/affirmation — случайная аффирмация\n"
        "/tips - случайный совет\n"
        "/breathe - дыхательное упражнение\n"
        "/mood - отметить настроение\n"
        "/stats - статистика настроения\n"
        "/help - помощь"
    )
    await update.message.reply_html(text)


async def affirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает случайную аффирмацию из внешнего API."""
    session = context.bot_data['aiohttp_session']
    try:
        async with session.get('https://www.affirmations.dev/') as response:
            response.raise_for_status()
            data = await response.json()
            affirmation_text = data['affirmation']

            await update.message.reply_text(affirmation_text)

    except aiohttp.ClientError as e:
        print(f"Ошибка при запросе к API: {e}")
        await update.message.reply_text("Не удалось получить аффирмацию. "
                                        "Попробуйте позже.")
    except KeyError:
        await update.message.reply_text("Что-то пошло не так с форматом ответа"
                                        ".Попробуйте ещё раз.")


async def tips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получает случайный совет из внешнего API."""
    session: aiohttp.ClientSession = context.bot_data['aiohttp_session']
    try:
        async with (session.get("https://api.adviceslip.com/advice")
                    as response):
            response.raise_for_status()
            data = await response.json()
            # Advice Slip API возвращает {"slip": {"advice": "..."}}
            advice = data["slip"]["advice"]
            await update.message.reply_text(f"💡 Совет: {advice}")
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка запроса к Advice Slip API: {e}")
        await update.message.reply_text(
            "Не удалось получить совет. Попробуйте позже."
        )
    except (KeyError, ValueError):
        await update.message.reply_text(
            "Сервис вернул неожиданный ответ. Попробуйте ещё раз."
        )


async def breathe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пошаговое дыхательное упражнение."""
    await update.message.reply_text("Приготовьтесь. "
                                    "Начинаем через 3 секунды...")
    await asyncio.sleep(3)
    for _ in range(3):
        await update.message.reply_text("Вдох... 🫁")
        await asyncio.sleep(3)
        await update.message.reply_text("Задержите дыхание... ⏳")
        await asyncio.sleep(2)
        await update.message.reply_text("Выдох... 💨")
        await asyncio.sleep(4)
    await update.message.reply_text("Упражнение завершено. Вы молодец! 🌟")


async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Предлагает выбрать настроение через инлайн-кнопки."""
    keyboard = [
        [
            InlineKeyboardButton("😢", callback_data="mood_1"),
            InlineKeyboardButton("😐", callback_data="mood_2"),
            InlineKeyboardButton("😊", callback_data="mood_3"),
        ]
    ]
    await update.message.reply_text(
        "Как вы себя чувствуете?", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки настроения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mapping = {
        "mood_1": (1, "Записал: Вам грустно. Все пройдет. 💙"),
        "mood_2": (2, "Записал: Нейтральное настроение. 😐"),
        "mood_3": (3, "Записал: Отличное настроение! Так держать! 🌟"),
    }
    score, text = mapping.get(query.data, (0, "Неизвестная кнопка."))
    if score:
        save_mood(user_id, score)
    await query.edit_message_text(text=text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает среднее настроение пользователя."""
    user_id = update.effective_user.id
    data = load_moods()
    user_moods = [entry["score"] for entry in data if entry["user_id"]
                  == user_id]

    if not user_moods:
        await update.message.reply_text("У вас пока нет записей о настроении.")
        return

    avg = sum(user_moods) / len(user_moods)
    await update.message.reply_text(
        f"Ваше среднее настроение: {avg:.2f} из 3.\n"
        f"Всего записей: {len(user_moods)}"
    )


async def post_init(application: Application) -> None:
    """Создаём сессию для HTTP-запросов при старте бота."""
    application.bot_data['aiohttp_session'] = aiohttp.ClientSession()


async def post_shutdown(application: Application) -> None:
    """Закрываем сессию при выключении бота."""
    await application.bot_data['aiohttp_session'].close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Команды:\n"
        "/start — начать\n"
        "/affirmation — аффирмация дня\n"
        "/tips — совет\n"
        "/breathe — дыхание\n"
        "/mood — настроение\n"
        "/stats — статистика"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("affirmation", affirmation))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tips", tips))
    application.add_handler(CommandHandler("breathe", breathe))
    application.add_handler(CommandHandler("mood", mood))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
