import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "telegram-webhook")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not available. Deploy this app as a Render Web Service.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇳🇬 Welcome to Nigeria Job Finder!\n\n"
        "I help you find current Nigerian and remote job opportunities.\n\n"
        "Use:\n"
        "🔎 /jobs - Current job opportunities\n"
        "🌍 /remote - Remote jobs\n"
        "🇳🇬 /nigeria - Jobs in Nigeria\n"
        "🔔 /alerts - Job alerts\n"
        "ℹ️ /help - Help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Nigeria Job Finder is being built to find fresh, legitimate job opportunities "
        "and filter out expired or suspicious listings.\n\n"
        "The job search engine will be connected next."
    )


async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔎 Job search is being connected. Soon I'll show current verified opportunities here."
    )


async def remote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 Remote-job search is coming next. We'll focus on opportunities that accept applicants from Nigeria."
    )


async def nigeria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🇳🇬 Nigerian job search is coming next.")


async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔔 Job alerts are coming next. You'll be able to choose job categories and receive new matching opportunities."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Nigeria Job Finder is online.")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("jobs", jobs))
    application.add_handler(CommandHandler("remote", remote))
    application.add_handler(CommandHandler("nigeria", nigeria))
    application.add_handler(CommandHandler("alerts", alerts))
    application.add_handler(CommandHandler("status", status))

    webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/{WEBHOOK_PATH}"
    logger.info("Starting Nigeria Job Finder webhook: %s", webhook_url)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
