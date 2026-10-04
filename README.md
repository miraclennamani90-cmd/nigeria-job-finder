# Nigeria Job Finder 🇳🇬

A Telegram job finder designed to help users discover current Nigerian and remote opportunities.

## Current MVP

- Telegram bot commands
- Secure bot-token environment variable
- Placeholder job-search commands

## Planned features

- Current Nigerian jobs
- Remote jobs accepting applicants from Nigeria
- Indeed and other permitted job sources
- Expiry/freshness checking
- Duplicate detection
- Employer/application verification
- Scam-risk checks
- Personalized job alerts
- WhatsApp integration
- Facebook integration

## Running locally

Set the environment variable `BOT_TOKEN` to your Telegram bot token, then install dependencies:

```bash
pip install -r requirements.txt
python bot.py
```

Never commit your Telegram bot token to GitHub.
