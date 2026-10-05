import os
import json
import logging
import urllib.request
import urllib.parse

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
    raise RuntimeError("RENDER_EXTERNAL_URL is not available.")


def get_remote_jobs():
    """Get current remote jobs from Remotive."""
    url = "https://remotive.com/api/remote-jobs"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NigeriaJobFinderBot/1.0"},
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data.get("jobs", [])


def format_job(job):
    title = job.get("title", "Untitled job")
    company = job.get("company_name", "Company not listed")
    location = job.get("candidate_required_location", "Remote")
    job_url = job.get("url", "")
    source_url = job_url or "https://remotive.com/"

    return (
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"🌍 {location}\n\n"
        f"🔗 <a href=\"{source_url}\">View job & apply</a>\n"
        f"📌 Source: Remotive"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇳🇬 <b>Welcome to Nigeria Job Finder!</b>\n\n"
        "I help you find current Nigerian and remote job opportunities.\n\n"
        "Use:\n"
        "🔎 /jobs - Current remote opportunities\n"
        "🌍 /remote - Remote jobs\n"
        "🇳🇬 /nigeria - Nigerian jobs\n"
        "🔔 /alerts - Job alerts\n"
        "ℹ️ /help - Help",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇳🇬 <b>Nigeria Job Finder</b>\n\n"
        "The bot is being built to find fresh, legitimate job opportunities "
        "and filter out expired or suspicious listings.\n\n"
        "Try /jobs or /remote to see available remote jobs.",
        parse_mode="HTML",
    )


async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Searching for current jobs...")

    try:
        jobs_list = get_remote_jobs()

        if not jobs_list:
            await update.message.reply_text(
                "Sorry, I couldn't find any jobs right now. Please try again later."
            )
            return

        # Show the first 5 jobs for now.
        for job in jobs_list[:5]:
            await update.message.reply_text(
                format_job(job),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    except Exception as error:
        logger.exception("Job search failed: %s", error)
        await update.message.reply_text(
            "⚠️ I couldn't retrieve the jobs right now. Please try again shortly."
        )


async def remote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await jobs(update, context)


async def nigeria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇳🇬 Nigerian job search is coming next.\n\n"
        "We're currently connecting the first live job source."
    )


async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔔 Job alerts are coming next.\n\n"
        "You'll eventually be able to choose job categories, "
        "locations and experience levels."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Nigeria Job Finder is online and running."
    )


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

    logger.info(
        "Starting Nigeria Job Finder webhook: %s",
        webhook_url,
    )

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
