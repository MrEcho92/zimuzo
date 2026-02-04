#!/bin/bash
set -e

# Wait for the PostgreSQL database to be available
chmod +x app/wait-for-it.sh
app/wait-for-it.sh db:5432 --timeout=60 --strict -- echo "PostgreSQL is up and running 🚀"

# Run database migrations
uv run alembic upgrade head

# Start app
echo "Starting app 🥁 🏃🏾‍♂️‍➡️ 🏃🏾‍♂️‍➡️ 🏃🏾‍♂️‍➡️..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo "App started ${🚀 * 3}"
