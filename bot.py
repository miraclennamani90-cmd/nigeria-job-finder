import os
import json
import logging
import urllib.request
import urllib.parse
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

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")

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

        logger.exception(
            "Database initialization failed."
        )


# ============================================================
# SAVE JOB
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

    if not DATABASE_URL:
        return False

    try:

        with psycopg.connect(DATABASE_URL) as conn:

            with conn.cursor() as cur:

                # Check if job already exists
                cur.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE source = %s
                    AND external_id = %s
                    LIMIT 1
                    """,
                    (
                        source,
                        external_id,
                    ),
                )

                existing = cur.fetchone()

                # ------------------------------------------------
                # EXISTING JOB
                # ------------------------------------------------

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

                # ------------------------------------------------
                # NEW JOB
                # ------------------------------------------------

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

        logger.exception(
            "Failed to save job."
        )

        return False


# ============================================================
# ADZUNA — NIGERIA
# ============================================================

def get_adzuna_jobs(
    page=1,
    results_per_page=10,
    search_term=""
):

    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:

        logger.warning(
            "Adzuna credentials are not configured."
        )

        return []

    base_url = (
        "https://api.adzuna.com/v1/api/"
        "jobs/ng/search/"
        f"{page}"
    )

    parameters = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": results_per_page,
        "content-type": "application/json",
        "sort_by": "date",
    }

    if search_term:

        parameters["what"] = search_term

    url = (
        base_url
        + "?"
        + urllib.parse.urlencode(parameters)
    )

    try:

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return data.get(
            "results",
            []
        )

    except Exception:

        logger.exception(
            "Failed to get Nigerian jobs from Adzuna."
        )

        return []


# ============================================================
# PROCESS ADZUNA JOB
# ============================================================

def process_adzuna_job(job):

    external_id = str(
        job.get("id")
        or job.get("redirect_url")
        or ""
    )

    title = job.get(
        "title",
        "Untitled position"
    )

    company_data = job.get(
        "company",
        {}
    )

    company = company_data.get(
        "display_name",
        "Unknown company"
    )

    location_data = job.get(
        "location",
        {}
    )

    location = location_data.get(
        "display_name",
        "Nigeria"
    )

    description = job.get(
        "description",
        ""
    )

    application_url = job.get(
        "redirect_url",
        ""
    )

    published_at = job.get(
        "created",
        ""
    )

    employment_type = job.get(
        "contract_time",
        ""
    )

    if not employment_type:

        employment_type = job.get(
            "contract_type",
            ""
        )

    category_data = job.get(
        "category",
        {}
    )

    experience_level = category_data.get(
        "label",
        ""
    )

    is_new = save_job(
        source="Adzuna",
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        country="Nigeria",
        remote=False,
        employment_type=employment_type,
        experience_level=experience_level,
        description=description,
        application_url=application_url,
        published_at=published_at,
        raw_job=job,
    )

    return is_new


# ============================================================
# REMOTIVE
# ============================================================

def get_remotive_jobs(limit=5):

    url = (
        "https://remotive.com/api/remote-jobs"
    )

    try:

        with urllib.request.urlopen(
            url,
            timeout=20
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        jobs = data.get(
            "jobs",
            []
        )

        return jobs[:limit]

    except Exception:

        logger.exception(
            "Failed to get jobs from Remotive."
        )

        return []


# ============================================================
# JOBICY
# ============================================================

def get_jobicy_jobs(limit=5):

    url = (
        "https://jobicy.com/api/v2/"
        "remote-jobs?count=10"
    )

    try:

        with urllib.request.urlopen(
            url,
            timeout=20
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        jobs = data.get(
            "jobs",
            []
        )

        return jobs[:limit]

    except Exception:

        logger.exception(
            "Failed to get jobs from Jobicy."
        )

        return []


# ============================================================
# FORMAT ADZUNA JOB
# ============================================================

def format_adzuna_job(job):

    title = job.get(
        "title",
        "Untitled position"
    )

    company = job.get(
        "company",
        {}
    ).get(
        "display_name",
        "Unknown company"
    )

    location = job.get(
        "location",
        {}
    ).get(
        "display_name",
        "Nigeria"
    )

    url = job.get(
        "redirect_url",
        ""
    )

    category = job.get(
        "category",
        {}
    ).get(
        "label",
        ""
    )

    salary_min = job.get(
        "salary_min"
    )

    salary_max = job.get(
        "salary_max"
    )

    message = (
        f"🇳🇬 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
    )

    if category:

        message += (
            f"📂 {category}\n"
        )

    if salary_min and salary_max:

        message += (
            f"💰 Salary: "
            f"{salary_min:,} - "
            f"{salary_max:,}\n"
        )

    elif salary_min:

        message += (
            f"💰 Salary from "
            f"{salary_min:,}\n"
        )

    message += (
        "🌐 Source: Adzuna\n"
        f"🔗 <a href=\"{url}\">"
        "Apply / View Job</a>"
    )

    return message


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

    url = job.get(
        "url",
        ""
    )

    salary = job.get(
        "salary",
        ""
    )

    message = (
        f"🌍 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
    )

    if salary:

        message += (
            f"💰 {salary}\n"
        )

    message += (
        "🌐 Source: Remotive\n"
        f"🔗 <a href=\"{url}\">"
        "Apply / View Job</a>"
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
        f"🌍 <b>{title}</b>\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
    )

    if salary:

        message += (
            f"💰 {salary}\n"
        )

    message += (
        "🌐 Source: Jobicy\n"
        f"🔗 <a href=\"{url}\">"
        "Apply / View Job</a>"
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
        "🇳🇬 /nigeria - Nigerian jobs\n"
        "🌍 /remote - Remote jobs\n"
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

        "/jobs - Search jobs\n"
        "/nigeria - Nigerian jobs\n"
        "/remote - Remote jobs\n"
        "/alerts - Job alerts\n"
        "/status - Check system status\n\n"

        "The bot collects jobs from multiple "
        "sources and stores them in its database."
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /NIGERIA
# ============================================================

async def nigeria(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🇳🇬 Searching current Nigerian jobs..."
    )

    jobs_found = get_adzuna_jobs(
        page=1,
        results_per_page=10
    )

    if not jobs_found:

        await update.message.reply_text(
            "⚠️ I couldn't retrieve Nigerian jobs "
            "from Adzuna right now.\n\n"
            "Please try again shortly."
        )

        return

    new_jobs = 0

    for job in jobs_found:

        if process_adzuna_job(job):

            new_jobs += 1

    await update.message.reply_text(
        f"🇳🇬 Found {len(jobs_found)} Nigerian jobs.\n"
        f"🆕 {new_jobs} new jobs added to the database."
    )

    for job in jobs_found:

        message = format_adzuna_job(
            job
        )

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

    await update.message.reply_text(
        "🌍 Searching remote jobs..."
    )

    remotive_jobs = get_remotive_jobs(
        limit=5
    )

    jobicy_jobs = get_jobicy_jobs(
        limit=5
    )

    total = (
        len(remotive_jobs)
        + len(jobicy_jobs)
    )

    if total == 0:

        await update.message.reply_text(
            "Sorry, no remote jobs were found "
            "right now."
        )

        return

    new_jobs = 0

    for job in remotive_jobs:

        external_id = str(
            job.get("id")
            or job.get("url")
            or ""
        )

        if save_job(
            source="Remotive",
            external_id=external_id,
            title=job.get(
                "title",
                "Untitled position"
            ),
            company=job.get(
                "company_name",
                "Unknown company"
            ),
            location=job.get(
                "candidate_required_location",
                "Remote"
            ),
            country="",
            remote=True,
            employment_type=job.get(
                "job_type",
                ""
            ),
            experience_level="",
            description=job.get(
                "description",
                ""
            ),
            application_url=job.get(
                "url",
                ""
            ),
            published_at=job.get(
                "publication_date",
                ""
            ),
            raw_job=job,
        ):

            new_jobs += 1

    for job in jobicy_jobs:

        external_id = str(
            job.get("id")
            or job.get("url")
            or ""
        )

        if save_job(
            source="Jobicy",
            external_id=external_id,
            title=job.get(
                "jobTitle",
                "Untitled position"
            ),
            company=job.get(
                "companyName",
                "Unknown company"
            ),
            location=job.get(
                "jobGeo",
                "Remote"
            ),
            country="",
            remote=True,
            employment_type=job.get(
                "jobType",
                ""
            ),
            experience_level="",
            description=job.get(
                "jobDescription",
                ""
            ),
            application_url=job.get(
                "url",
                ""
            ),
            published_at=job.get(
                "pubDate",
                ""
            ),
            raw_job=job,
        ):

            new_jobs += 1

    await update.message.reply_text(
        f"🌍 Found {total} remote jobs.\n"
        f"🆕 {new_jobs} new jobs added."
    )

    for job in remotive_jobs:

        await update.message.reply_text(
            format_remotive_job(job),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    for job in jobicy_jobs:

        await update.message.reply_text(
            format_jobicy_job(job),
            parse_mode="HTML",
            disable_web_page_preview=True
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

    # Nigerian jobs
    nigeria_jobs = get_adzuna_jobs(
        page=1,
        results_per_page=5
    )

    # Remote jobs
    remotive_jobs = get_remotive_jobs(
        limit=3
    )

    jobicy_jobs = get_jobicy_jobs(
        limit=2
    )

    total = (
        len(nigeria_jobs)
        + len(remotive_jobs)
        + len(jobicy_jobs)
    )

    if total == 0:

        await update.message.reply_text(
            "No jobs were found right now."
        )

        return

    new_jobs = 0

    # Save Nigerian jobs
    for job in nigeria_jobs:

        if process_adzuna_job(job):

            new_jobs += 1

    # Save Remotive jobs
    for job in remotive_jobs:

        external_id = str(
            job.get("id")
            or job.get("url")
            or ""
        )

        if save_job(
            source="Remotive",
            external_id=external_id,
            title=job.get(
                "title",
                "Untitled position"
            ),
            company=job.get(
                "company_name",
                "Unknown company"
            ),
            location=job.get(
                "candidate_required_location",
                "Remote"
            ),
            country="",
            remote=True,
            employment_type=job.get(
                "job_type",
                ""
            ),
            experience_level="",
            description=job.get(
                "description",
                ""
            ),
            application_url=job.get(
                "url",
                ""
            ),
            published_at=job.get(
                "publication_date",
                ""
            ),
            raw_job=job,
        ):

            new_jobs += 1

    # Save Jobicy jobs
    for job in jobicy_jobs:

        external_id = str(
            job.get("id")
            or job.get("url")
            or ""
        )

        if save_job(
            source="Jobicy",
            external_id=external_id,
            title=job.get(
                "jobTitle",
                "Untitled position"
            ),
            company=job.get(
                "companyName",
                "Unknown company"
            ),
            location=job.get(
                "jobGeo",
                "Remote"
            ),
            country="",
            remote=True,
            employment_type=job.get(
                "jobType",
                ""
            ),
            experience_level="",
            description=job.get(
                "jobDescription",
                ""
            ),
            application_url=job.get(
                "url",
                ""
            ),
            published_at=job.get(
                "pubDate",
                ""
            ),
            raw_job=job,
        ):

            new_jobs += 1

    await update.message.reply_text(
        f"✅ Found {total} jobs.\n"
        f"🆕 {new_jobs} new jobs added to the database."
    )

    # Show Nigerian jobs
    for job in nigeria_jobs:

        await update.message.reply_text(
            format_adzuna_job(job),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    # Show remote jobs
    for job in remotive_jobs:

        await update.message.reply_text(
            format_remotive_job(job),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    for job in jobicy_jobs:

        await update.message.reply_text(
            format_jobicy_job(job),
            parse_mode="HTML",
            disable_web_page_preview=True
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

    adzuna_status = "❌ Not configured"

    if (
        ADZUNA_APP_ID
        and ADZUNA_APP_KEY
    ):

        adzuna_status = "✅ Configured"

    message = (
        "🇳🇬 <b>Nigeria Job Finder Status</b>\n\n"
        "🤖 Bot: Online\n"
        f"🗄 Database: {database_status}\n"
        f"🇳🇬 Adzuna: {adzuna_status}"
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

    # Register commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "jobs",
            jobs
        )
    )

    application.add_handler(
        CommandHandler(
            "nigeria",
            nigeria
        )
    )

    application.add_handler(
        CommandHandler(
            "remote",
            remote
        )
    )

    application.add_handler(
        CommandHandler(
            "alerts",
            alerts
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
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
