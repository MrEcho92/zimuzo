FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1


RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY app ./app
COPY start.sh ./
COPY alembic.ini ./
COPY alembic ./alembic

RUN chmod +x start.sh

# Create non-root user and change ownership
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Add uv's virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["./start.sh"]
