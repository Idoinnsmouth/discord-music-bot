# Discord Music Bot

Discord music bot with slash commands, voice playback, queueing, and a FastAPI control API.

## Features
- Slash commands (`/join`, `/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/leave`, `/queue`)
- YouTube URL or search-term playback via `yt-dlp`
- Per-guild queue and now-playing tracking
- Voice reconnect options for more stable streams
- FastAPI control API for external web control panels

## Project Structure
```text
discord-music-bot/
├── backend/
│   ├── discord_music_bot/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── api.py
│   │   ├── bot.py
│   │   ├── config.py
│   │   └── music.py
│   ├── main.py
│   ├── pyproject.toml
│   └── uv.lock
└── Dockerfile
```

## Prerequisites
- Python 3.11+
- `ffmpeg` installed and available on `PATH`
- Discord bot token
- Bot invited with OAuth2 scopes: `bot` and `applications.commands`

## Environment Variables
- `DISCORD_TOKEN` (required): your bot token
- `DISCORD_GUILD_ID` (optional): guild/server id for faster command sync during development
- `CONTROL_API_HOST` (optional, default `0.0.0.0`): FastAPI bind host
- `CONTROL_API_PORT` (optional, default `8000`): FastAPI bind port
- `CONTROL_API_TOKEN` (optional): if set, requests to control endpoints must include `X-API-Key`

## Run
Install dependencies:

```bash
cd backend
uv sync
```

Run Discord bot + FastAPI API together:

```bash
uv run main.py
```

## Lint
Install dev tools:

```bash
cd backend
uv sync --extra dev
```

Run Ruff:

```bash
cd backend
uv run ruff check .
```

## Control API
If `CONTROL_API_TOKEN` is set, include it as `X-API-Key`.

- `GET /health`
- `GET /guilds/{guild_id}/queue`
- `POST /guilds/{guild_id}/play`
- `POST /guilds/{guild_id}/pause`
- `POST /guilds/{guild_id}/resume`
- `POST /guilds/{guild_id}/skip`
- `POST /guilds/{guild_id}/stop`

Example:

```bash
curl -X POST "http://localhost:8000/guilds/<guild_id>/play" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <token>" \
  -d '{"query":"lofi hip hop","requested_by":"Web Panel","voice_channel_id":123456789012345678}'
```

## Docker
Build the image:

```bash
docker build -t discord-music-bot .
```

The image installs `ffmpeg` and `nodejs` so `yt-dlp` can solve YouTube JS challenges.

Run the bot + API (from repo root, using your existing `.env` file):

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
