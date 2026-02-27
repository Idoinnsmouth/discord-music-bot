FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md main.py ./
COPY discord_music_bot ./discord_music_bot

RUN pip install --no-cache-dir .

CMD ["python", "main.py"]
