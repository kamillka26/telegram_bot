import logging
import aiohttp

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters

from config import BOT_TOKEN

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )

async def affirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        await update.message.reply_text("Не удалось получить аффирмацию. Попробуйте позже.")
    except KeyError:
        await update.message.reply_text("Что-то пошло не так с форматом ответа. Попробуйте ещё раз.")

async def post_init(application: Application) -> None:
    """Создаём сессию для HTTP-запросов при старте бота."""
    application.bot_data['aiohttp_session'] = aiohttp.ClientSession()


async def post_shutdown(application: Application) -> None:
    """Закрываем сессию при выключении бота."""
    await application.bot_data['aiohttp_session'].close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


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

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
