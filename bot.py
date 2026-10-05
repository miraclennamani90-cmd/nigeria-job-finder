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


# ---------------------------------------------------------
# REMOTIVE
# ---------------------------------------------------------

def get_remotive_jobs():
    url = "https://remotive.com/api/remote-jobs"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NigeriaJobFinderBot/1.0"},
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data.get("jobs", [])


# ---------------------------------------------------------
# JOBICY
# ---------------------------------------------------------

def get_jobicy_jobs():
    params = urllib.parse.urlencode({
        "count": "10"
    })

    url = f"https://jobicy.com/api/v2/remote-jobs?{params}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NigeriaJobFinderBot/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data.get("jobs", [])


# ---------------------------------------------------------
# FORMAT REMOTIVE JOB
# ---------------------------------------------------------

def format_remotive_job(job):
    title = job.get("title", "Untitled job")
    company = job.get("company_name", "Company not listed")
    location = job.get(
        "candidate_required_location",
        "Remote"
    )
    job_url = job.get("url", "https://remotive.com/")

    return (
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"🌍 {location}\n\n"
        f"🔗 <a href=\"{job_url}\">View job & apply</a>\n"
        f"📌 Source: Remotive"
    )


# ---------------------------------------------------------
# FORMAT JOBICY JOB
# ---------------------------------------------------------

def format_jobicy_job(job):
    title = job.get("jobTitle", "Untitled job")
    company = job.get("companyName", "Company not listed")
    location = job.get("jobGeo", "Remote")
    job_url = job.get(
        "url",
        "https://jobicy.com/jobs"
    )

    salary_min = job.get("salaryMin")
    salary_max = job.get("salaryMax")
    salary_currency = job.get("salaryCurrency")

    salary_text = ""

    if salary_min and salary_max and salary_currency:
        salary_text = (
            f"💰 {salary_currency} "
            f"{salary_min:,} - {salary_max:,}\n"
        )

    return (
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"🌍 {location}\n"
        f"{salary_text}\n"
        f"🔗 <a href=\"{job_url}\">View job & apply</a>\n"
        f"📌 Source: Jobicy"
    )


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇳🇬 <b>Welcome to Nigeria Job Finder!</b>\n\n"
        "I help you find current Nigerian and remote job opportunities.\n\n"
        "Use:\n"
        "🔎 /jobs - Current job opportunities\n"
        "🌍 /remote - Remote jobs\n"
        "🇳🇬 /nigeria - Nigerian jobs\n"
        "🔔 /alerts - Job alerts\n"
        "ℹ️ /help - Help",
        parse_mode="HTML",
    )


# ---------------------------------------------------------
# HELP
# ---------------------------------------------------------

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "🇳🇬 <b>Nigeria Job Finder</b>\n\n"
        "The bot searches multiple job sources for fresh opportunities.\n\n"
        "Try /jobs or /remote to see available jobs.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------
# JOBS
# ---------------------------------------------------------

async def jobs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 Searching multiple job sources..."
    )

    all_jobs = []

    # Remotive
    try:
        remotive_jobs = get_remotive_jobs()

        for job in remotive_jobs[:5]:
            all_jobs.append(
                format_remotive_job(job)
            )

    except Exception as error:
        logger.exception(
            "Remotive search failed: %s",
            error
        )

    # Jobicy
    try:
        jobicy_jobs = get_jobicy_jobs()

        for job in jobicy_jobs[:5]:
            all_jobs.append(
                format_jobicy_job(job)
            )

    except Exception as error:
        logger.exception(
            "Jobicy search failed: %s",
            error
        )

    if not all_jobs:
        await update.message.reply_text(
            "⚠️ I couldn't retrieve jobs right now. "
            "Please try again shortly."
        )
        return

    # Show up to 10 jobs.
    for job_message in all_jobs[:10]:

        await update.message.reply_text(
            job_message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


# ---------------------------------------------------------
# REMOTE
# ---------------------------------------------------------

async def remote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await jobs(update, context)


# ---------------------------------------------------------
# NIGERIA
# ---------------------------------------------------------

async def nigeria(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🇳🇬 Nigerian job search is being connected next.\n\n"
        "The bot already has two live remote job sources."
    )


# ---------------------------------------------------------
# ALERTS
# ---------------------------------------------------------

async def alerts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔔 Job alerts are coming next.\n\n"
        "You'll eventually be able to choose "
        "job categories, locations and experience levels."
    )


# ---------------------------------------------------------
# STATUS
# ---------------------------------------------------------

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "✅ Nigeria Job Finder is online and running."
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("jobs", jobs)
    )

    application.add_handler(
        CommandHandler("remote", remote)
    )

    application.add_handler(
        CommandHandler("nigeria", nigeria)
    )

    application.add_handler(
        CommandHandler("alerts", alerts)
    )

    application.add_handler(
        CommandHandler("status", status)
    )

    webhook_url = (
        f"{RENDER_EXTERNAL_URL.rstrip('/')}"
        f"/{WEBHOOK_PATH}"
    )

    logger.info(
        "Starting Nigeria Job Finder webhook: %s",
        webhook_url
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
