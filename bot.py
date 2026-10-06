import os
import json
import logging
import urllib.request
import psycopg

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", "10000"))
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "telegram")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def init_database():
    """Create the jobs table if it does not already exist."""

    if not DATABASE_URL:
        logger.warning("DATABASE_URL is not set.")
        return

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id BIGSERIAL PRIMARY KEY,

                        source TEXT NOT NULL,
                        external_id TEXT,

                        title TEXT NOT NULL,
                        company TEXT,
                        location TEXT,
                        country TEXT,

                        remote BOOLEAN DEFAULT FALSE,

                        employment_type TEXT,
                        experience_level TEXT,

                        description TEXT,
                        application_url TEXT,

                        published_at TEXT,

                        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        is_active BOOLEAN DEFAULT TRUE,

                        verification_score INTEGER DEFAULT 0,
                        scam_risk TEXT DEFAULT 'unknown',

                        raw_json JSONB,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            conn.commit()

        logger.info("Database initialized successfully.")

    except Exception:
        logger.exception("Database initialization failed.")


# ============================================================
# SAVE JOB TO DATABASE
# ============================================================

def save_job(
    source,
    external_id,
    title,
    company,
    location,
    country,
    remote,
    employment_type,
    experience_level,
    description,
    application_url,
    published_at,
    raw_job,
):
    """
    Save a job to PostgreSQL.

    If the same source + external ID already exists,
    update the existing job instead of creating a duplicate.
    """

    if not DATABASE_URL:
        return False

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                # Check whether this job already exists
                cur.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE source = %s
                    AND external_id = %s
                    LIMIT 1
                    """,
                    (source, external_id),
                )

                existing = cur.fetchone()

                if existing:

                    cur.execute(
                        """
                        UPDATE jobs
                        SET
                            title = %s,
                            company = %s,
                            location = %s,
                            country = %s,
                            remote = %s,
                            employment_type = %s,
                            experience_level = %s,
                            description = %s,
                            application_url = %s,
                            published_at = %s,
                            last_seen_at = CURRENT_TIMESTAMP,
                            is_active = TRUE,
                            raw_json = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            title,
                            company,
                            location,
                            country,
                            remote,
                            employment_type,
                            experience_level,
                            description,
                            application_url,
                            published_at,
                            json.dumps(raw_job),
                            existing[0],
                        ),
                    )

                    conn.commit()

                    return False

                # New job
                cur.execute(
                    """
                    INSERT INTO jobs (
                        source,
                        external_id,
                        title,
                        company,
                        location,
                        country,
                        remote,
                        employment_type,
                        experience_level,
                        description,
                        application_url,
                        published_at,
                        raw_json
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        source,
                        external_id,
                        title,
                        company,
                        location,
                        country,
                        remote,
                        employment_type,
                        experience_level,
                        description,
                        application_url,
                        published_at,
                        json.dumps(raw_job),
                    ),
                )

            conn.commit()

        return True

    except Exception:
        logger.exception("Failed to save job.")
        return False


# ============================================================
# REMOTIVE
# ============================================================

def get_remotive_jobs(limit=10):

    url = "https://remotive.com/api/remote-jobs"

    try:

        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        jobs = data.get("jobs", [])

        return jobs[:limit]

    except Exception:

        logger.exception(
            "Failed to get jobs from Remotive."
        )

        return []


# ============================================================
# JOBICY
# ============================================================

def get_jobicy_jobs(limit=10):

    url = (
        "https://jobicy.com/api/v2/"
        "remote-jobs?count=10"
    )

    try:

        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        jobs = data.get("jobs", [])

        return jobs[:limit]

    except Exception:

        logger.exception(
            "Failed to get jobs from Jobicy."
        )

        return []


# ============================================================
# REMOTIVE → DATABASE
# ============================================================

def process_remotive_job(job):

    external_id = str(
        job.get("id")
        or job.get("url")
        or ""
    )

    title = job.get(
        "title",
        "Untitled position"
    )

    company = job.get(
        "company_name",
        "Unknown company"
    )

    location = job.get(
        "candidate_required_location",
        "Remote"
    )

    description = job.get(
        "description",
        ""
    )

    application_url = job.get(
        "url",
        ""
    )

    published_at = job.get(
        "publication_date",
        ""
    )

    employment_type = job.get(
        "job_type",
        ""
    )

    is_new = save_job(
        source="Remotive",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        country="",
        remote=True,
        employment_type=employment_type,
        experience_level="",
        description=description,
        application_url=application_url,
        published_at=published_at,
        raw_job=job,
    )

    return is_new


# ============================================================
# JOBICY → DATABASE
# ============================================================

def process_jobicy_job(job):

    external_id = str(
        job.get("id")
        or job.get("url")
        or ""
    )

    title = job.get(
        "jobTitle",
        "Untitled position"
    )

    company = job.get(
        "companyName",
        "Unknown company"
    )

    location = job.get(
        "jobGeo",
        "Remote"
    )

    description = job.get(
        "jobDescription",
        ""
    )

    application_url = job.get(
        "url",
        ""
    )

    published_at = job.get(
        "pubDate",
        ""
    )

    employment_type = job.get(
        "jobType",
        ""
    )

    is_new = save_job(
        source="Jobicy",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        country="",
        remote=True,
        employment_type=employment_type,
        experience_level="",
        description=description,
        application_url=application_url,
        published_at=published_at,
        raw_job=job,
    )

    return is_new


# ============================================================
# FORMAT REMOTIVE JOB
# ============================================================

def format_remotive_job(job):

    title = job.get(
        "title",
        "Untitled position"
    )

    company = job.get(
        "company_name",
        "Unknown company"
    )

    location = job.get(
        "candidate_required_location",
        "Remote"
    )

    url = job.get("url", "")

    salary = job.get(
        "salary",
        ""
    )

    message = (
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
    )

    if salary:
        message += f"💰 {salary}\n"

    message += (
        "🌐 Source: Remotive\n"
        f"🔗 <a href=\"{url}\">Apply / View Job</a>"
    )

    return message


# ============================================================
# FORMAT JOBICY JOB
# ============================================================

def format_jobicy_job(job):

    title = job.get(
        "jobTitle",
        "Untitled position"
    )

    company = job.get(
        "companyName",
        "Unknown company"
    )

    location = job.get(
        "jobGeo",
        "Remote"
    )

    url = job.get(
        "url",
        ""
    )

    salary = job.get(
        "annualSalary",
        ""
    )

    message = (
        f"💼 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
    )

    if salary:
        message += f"💰 {salary}\n"

    message += (
        "🌐 Source: Jobicy\n"
        f"🔗 <a href=\"{url}\">Apply / View Job</a>"
    )

    return message


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = (
        "🇳🇬 <b>Welcome to Nigeria Job Finder!</b>\n\n"

        "I help you find current job opportunities "
        "for Nigerians and remote jobs.\n\n"

        "Available commands:\n"
        "🔎 /jobs - Find current jobs\n"
        "🌍 /remote - Find remote jobs\n"
        "🇳🇬 /nigeria - Find Nigerian jobs\n"
        "🔔 /alerts - Job alerts\n"
        "ℹ️ /help - Help\n"
        "📊 /status - Bot status"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = (
        "🇳🇬 <b>Nigeria Job Finder Help</b>\n\n"

        "/jobs - Search current jobs\n"
        "/remote - Search remote jobs\n"
        "/nigeria - Search jobs in Nigeria\n"
        "/alerts - Manage job alerts\n"
        "/status - Check bot status\n\n"

        "The job database now tracks jobs so we can "
        "detect duplicates and monitor job freshness."
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /JOBS
# ============================================================

async def jobs(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 Searching current jobs..."
    )

    remotive_jobs = get_remotive_jobs(
        limit=5
    )

    jobicy_jobs = get_jobicy_jobs(
        limit=5
    )

    new_jobs = 0
    total_jobs = (
        len(remotive_jobs)
        + len(jobicy_jobs)
    )

    # Save Remotive jobs
    for job in remotive_jobs:

        if process_remotive_job(job):
            new_jobs += 1

    # Save Jobicy jobs
    for job in jobicy_jobs:

        if process_jobicy_job(job):
            new_jobs += 1

    if total_jobs == 0:

        await update.message.reply_text(
            "Sorry, I couldn't find jobs right now. "
            "Please try again later."
        )

        return

    await update.message.reply_text(
        f"✅ Found {total_jobs} jobs.\n"
        f"🆕 {new_jobs} new jobs added to the database."
    )

    # Display Remotive
    for job in remotive_jobs:

        message = format_remotive_job(job)

        await update.message.reply_text(
            message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # Display Jobicy
    for job in jobicy_jobs:

        message = format_jobicy_job(job)

        await update.message.reply_text(
            message,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


# ============================================================
# /REMOTE
# ============================================================

async def remote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await jobs(update, context)


# ============================================================
# /NIGERIA
# ============================================================

async def nigeria(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🇳🇬 Nigerian job sources are being connected next.\n\n"
        "The database and remote-job collection system "
        "are now working."
    )


# ============================================================
# /ALERTS
# ============================================================

async def alerts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔔 Job alerts are coming soon.\n\n"

        "You will eventually be able to choose:\n"
        "• Job category\n"
        "• Location\n"
        "• Remote / Nigeria\n"
        "• Entry-level jobs\n"
        "• Full-time / part-time / contract\n"
        "• Frequency of alerts"
    )


# ============================================================
# /STATUS
# ============================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    database_status = "❌ Not connected"

    if DATABASE_URL:

        try:

            with psycopg.connect(
                DATABASE_URL
            ) as conn:

                with conn.cursor() as cur:

                    cur.execute(
                        "SELECT 1"
                    )

            database_status = "✅ Connected"

        except Exception:

            database_status = (
                "❌ Connection failed"
            )

    message = (
        "🇳🇬 <b>Nigeria Job Finder Status</b>\n\n"
        "🤖 Bot: Online\n"
        f"🗄 Database: {database_status}"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set."
        )

    if not RENDER_EXTERNAL_URL:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL is not set."
        )

    # Initialize database
    init_database()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
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

    # Webhook URL
    webhook_url = (
        RENDER_EXTERNAL_URL.rstrip("/")
        + "/"
        + WEBHOOK_PATH
    )

    logger.info(
        "Starting webhook at %s",
        webhook_url
    )

    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
