# WhatsApp Messaging Bot (Bird.com + Telegram)

A Telegram bot that sends pre-approved WhatsApp template messages through the [Bird.com](https://bird.com) API. Supports single and bulk sends, dynamic template variables, rate limiting, and full logging.

---

## Features

| Feature | Details |
|---------|---------|
| Telegram bot commands | `/send`, `/bulk`, `/setvars`, `/status`, `/help` |
| Bird.com WhatsApp API | Pre-approved template messages |
| Bulk contact upload | CSV or Excel (`.xlsx`) files |
| Rate limiting | Configurable per-second and per-minute limits |
| Logging | Rotating file + console logs |
| Docker support | `Dockerfile` + `docker-compose.yml` |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Axeb2b/codebhai-
cd codebhai-
cp .env.example .env
# Edit .env with your credentials
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the bot

```bash
python bot.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `BIRD_API_KEY` | Bird.com API access key |
| `BIRD_WORKSPACE_ID` | Bird.com workspace ID |
| `BIRD_CHANNEL_ID` | Bird.com WhatsApp channel ID |
| `WHATSAPP_TEMPLATE_ID` | Approved template identifier |
| `WHATSAPP_TEMPLATE_LANGUAGE` | Template language code (default `en`) |
| `RATE_LIMIT_MESSAGES_PER_SECOND` | Max messages per second (default `10`) |
| `RATE_LIMIT_MESSAGES_PER_MINUTE` | Max messages per minute (default `100`) |
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | Path to the log file (default `bot.log`) |

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List all commands |
| `/send <phone> [var1] [var2] ...` | Send a message to one number |
| `/setvars var1 var2 ...` | Save default template variables |
| `/bulk` | Start a bulk send (then upload a CSV/Excel file) |
| `/status` | Show rate-limiter counters |

### Sending a single message

```
/send +14155552671 John 20OFF
```

This sends the configured WhatsApp template to `+14155552671`, substituting `John` and `20OFF` as template variables.

### Bulk sending

1. Run `/bulk`
2. Upload a `.csv` or `.xlsx` file

**CSV format:**
```csv
phone,name
+14155552671,Alice
+442071234567,Bob
```

**Excel format:** same column headers (`phone`, `name`).

---

## Docker Deployment

```bash
cp .env.example .env
# Edit .env

docker-compose up -d
```

Logs are written to `./logs/bot.log` on the host.

---

## Project Structure

```
.
├── bot.py               # Telegram bot entry point
├── bird_api.py          # Bird.com API client
├── contact_parser.py    # CSV/Excel contact parser
├── rate_limiter.py      # Async sliding-window rate limiter
├── logger.py            # Logging configuration
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── tests/
    ├── test_bird_api.py
    ├── test_rate_limiter.py
    └── test_contact_parser.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Security Notes

- **Never** commit your `.env` file. It is listed in `.gitignore`.
- API keys and tokens are read exclusively from environment variables.
- The Docker container runs as a non-root user (`botuser`).
