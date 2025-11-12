# zimuzo backend

## Overview
This backend application is built using FastAPI. It provides a RESTful API for managing resources for AI agents interactions.

## Quick Start

### Prerequisites
- Python 3.10+
- UV
- Docker & Docker Compose
- Make (optional, but recommended)

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

3. **Start development environment**
```bash
   make docker-compose-up
```
Alternatively

If you have docker desktop installed locally, then run command `docker-compose up`. This command sets up database, application and pgadmin for the database.

Useful commands if you want to run locally:

```
To run makemigrations and apply migrations

docker-compose exec app uv run alembic revision --autogenerate -m
docker-compose exec app uv run alembic upgrade head

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
