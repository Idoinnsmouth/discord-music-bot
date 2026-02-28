FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY backend/README.md ./backend/README.md
COPY backend/main.py ./backend/main.py
COPY backend/discord_music_bot ./backend/discord_music_bot

RUN uv sync --project backend --frozen --no-dev

CMD ["uv", "run", "--project", "backend", "backend/main.py"]
