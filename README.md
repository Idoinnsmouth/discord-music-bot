# Discord Music Bot

Simple Discord music bot with slash commands, voice playback, queueing, and pause/resume.

## Features
- Slash commands (`/join`, `/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/leave`, `/queue`)
- YouTube URL or search-term playback via `yt-dlp`
- Per-guild queue and now-playing tracking
- Voice reconnect options for more stable streams

## Project Structure
```text
discord-music-bot/
├── discord_music_bot/
│   ├── __init__.py
│   ├── __main__.py
│   ├── bot.py
│   ├── config.py
│   └── music.py
├── main.py
└── pyproject.toml
```

## Prerequisites
- Python 3.11+
- `ffmpeg` installed and available on `PATH`
- Discord bot token
- Bot invited with OAuth2 scopes: `bot` and `applications.commands`

## Environment Variables
- `DISCORD_TOKEN` (required): your bot token
- `DISCORD_GUILD_ID` (optional): guild/server id for faster command sync during development

## Run
If your directory is not inside another `uv` workspace:

```bash
uv run main.py
```

You can also run the package entrypoint:

```bash
python -m discord_music_bot
```

## Lint
Install dev tools:

```bash
uv pip install -e ".[dev]"
```

Run Ruff:

```bash
uv run --no-project --with ruff ruff check .
```

## Docker
Build the image:

```bash
docker build -t discord-music-bot .
```

The image installs `ffmpeg` and `nodejs` so `yt-dlp` can solve YouTube JS challenges.

Run the bot (from your repo root, using your existing `.env` file):

```bash
docker run --rm --env-file .env discord-music-bot
```

## Slash Commands
- `/join`: Join your voice channel
- `/play <query>`: Queue a track from URL or search
- `/pause`: Pause current playback
- `/resume`: Resume paused playback
- `/skip`: Skip current track
- `/volume <0-200>`: Set playback volume percent
- `/stop`: Stop playback and clear queue
- `/leave`: Disconnect and clear queue
- `/queue`: Show now-playing and next tracks
