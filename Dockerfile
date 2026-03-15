FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy project metadata first (cache layer — only invalidated when deps change)
COPY pyproject.toml .

# Install backend deps only (no desktop extras: no PyAudio/mss/Pillow on Cloud Run)
RUN uv sync --no-dev --no-install-project

# Copy backend source
COPY backend/ ./backend/

ENV PORT=8080
EXPOSE 8080

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
