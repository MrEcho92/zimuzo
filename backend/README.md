# zimuzo backend

## Overview
This backend application is built using FastAPI. It provides a RESTful API for managing resources for AI agents interactions.

## Quick Start

### Prerequisites
- Python 3.10+
- UV
- Docker & Docker Compose
- Make (optional, but recommended)
- API Framework: FastAPI
- Database: PostgreSQL
- Task Queue: Celery + Redis
- Email Provider: Resend
- Monitoring: Flower (Celery dashboard)

### Setup

1. **Clone the repository**
```bash
   git clone
   cd backend
```

2. **Copy environment file**
```bash
   cp .env.example .env
```

3. **Configure environment variable**
Edit `.env`

4. **Start development environment**
```bash
   make docker-compose-up
```
Alternatively

If you have docker desktop installed locally, then run command `docker-compose up -d`. This command sets up database, application and pgadmin for the database.

Useful commands if you want to run locally:

```
To run makemigrations and apply migrations

docker-compose exec app uv run alembic revision --autogenerate -m
docker-compose exec app uv run alembic upgrade head

```

5. **Verify services**
```bash
# API health check
curl http://localhost:8000/health

# Flower dashboard (Celery monitoring)
open http://localhost:5555

# API documentation
open http://localhost:8000/api/docs

# Pgadmin
open http://localhost:5050/

```


## Development

### Running Tests
```bash
make tests
```

### Linting
```bash
make lint
```

### Formatting
```bash
make format
```

### Stop Environment
```bash
make docker-compose-down
```
OR

Removing all images, volumes, and orphans
```bash
make docker-compose-down-full
```

### Clean Up
```bash
make clean
```

## CI/CD

The project uses GitHub Actions for continuous integration:

- **Lint**: Runs Ruff and MyPy
- **Test**: Runs pytest with coverage

## Architecture Overview: Outbound/Inbound Email Handling

```
┌─────────────────────────────────────────────────────────────┐
│                    OUTBOUND FLOW                            │
├─────────────────────────────────────────────────────────────┤
│ 1. POST /messages                              │
│    ↓                                                        │
│ 2. Store Message(status=QUEUED) in PostgreSQL               │
│    ↓                                                        │
│ 3. Enqueue send_email_task → Celery → Redis                 │
│    ↓                                                        │
│ 4. Worker picks task → Resend API → Email sent              │
│    ↓                                                        │
│ 5. Update Message.status (SENT/FAILED)                      │
│    ↓                                                        │
│ 6. Store Event + Queue webhook delivery with retry          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    INBOUND FLOW                             │
├─────────────────────────────────────────────────────────────┤
│ 1. External email → inbox.agent@yourdomain.dev              │
│    ↓                                                        │
│ 2. Resend receives → Webhook                                |
|        → POST /webhooks/resend/email-received               │
│    ↓                                                        │
│ 3. Store Message(direction=inbound) + Thread                │
│    ↓                                                        │
│ 4. Enqueue process_inbound_email_task                       │
│    ↓                                                        │
│ 5. API parses: OTP codes, links, metadata                   │
│    ↓                                                        │
│ 6. Store parsed_metadata + Emit message.received event      │
│    ↓                                                        │
│ 7. Deliver webhook to customer's URL                        │
└─────────────────────────────────────────────────────────────┘
```

## Resend Configuration

### 1. Domain Setup

1. Go to https://resend.com/domains
2. Add your domain: `yourdomain.dev`
3. Add DNS records:

```dns
# MX Record (for receiving emails)
yourdomain.dev.  MX  10  feedback-smtp.us-east-1.amazonses.com

# SPF Record
yourdomain.dev.  TXT  "v=spf1 include:amazonses.com ~all"

# DKIM Records (provided by Resend)
resend._domainkey.yourdomain.dev  CNAME  xxx.resend.dev
```

### 2. Inbound Email Route

1. Go to https://resend.com/docs/dashboard/receiving/introduction

### 3. Webhook Configuration

1. Go to https://resend.com/webhooks
2. Add webhook: (use ngrok for development)
   - **URL**: `https://your-api.com/api/v1/webhooks/resend/email-received`
   - **Events**: Select `email.received`, `email.delivered`,`email.sent`
