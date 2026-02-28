import asyncio
from typing import Any

import discord
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .config import Settings
from .music import MusicManager, Track


class PlayRequest(BaseModel):
    query: str = Field(min_length=1)
    requested_by: str = Field(default="Control Panel", min_length=1)
    voice_channel_id: int | None = None
    text_channel_id: int | None = None


class TrackPayload(BaseModel):
    title: str
    webpage_url: str
    requested_by: str


class QueueResponse(BaseModel):
    guild_id: int
    volume_percent: int
    now_playing: TrackPayload | None
    queue: list[TrackPayload]


def _track_payload(track: Track) -> TrackPayload:
    return TrackPayload(
        title=track.title,
        webpage_url=track.webpage_url,
        requested_by=track.requested_by,
    )


def _ensure_guild(bot: discord.Client, guild_id: int) -> discord.Guild:
    guild = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guild {guild_id} is not available to the bot.",
        )
    return guild


def _connected_voice_client(guild: discord.Guild) -> discord.VoiceClient | None:
    vc_protocol = guild.voice_client
    if isinstance(vc_protocol, discord.VoiceClient) and vc_protocol.is_connected():
        return vc_protocol
    return None


async def _load_voice_channel(
    bot: discord.Client,
    guild: discord.Guild,
    voice_channel_id: int,
) -> discord.VoiceChannel | discord.StageChannel:
    channel = guild.get_channel(voice_channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(voice_channel_id)
        except discord.DiscordException as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Voice channel {voice_channel_id} was not found.",
            ) from exc

    if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="voice_channel_id must reference a voice or stage channel.",
        )

    if channel.guild.id != guild.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="voice_channel_id does not belong to this guild.",
        )

    return channel


def _default_text_channel_id(guild: discord.Guild) -> int | None:
    if guild.system_channel:
        return guild.system_channel.id
    if guild.text_channels:
        return guild.text_channels[0].id
    return None


async def _ensure_voice_connection(
    bot: discord.Client,
    guild: discord.Guild,
    voice_channel_id: int | None,
) -> discord.VoiceClient:
    active = _connected_voice_client(guild)
    if active:
        if voice_channel_id and active.channel and active.channel.id != voice_channel_id:
            target_channel = await _load_voice_channel(bot, guild, voice_channel_id)
            try:
                await active.move_to(target_channel)
            except discord.DiscordException as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to move to voice channel {voice_channel_id}.",
                ) from exc
        return active

    if voice_channel_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot is not connected. Provide voice_channel_id to connect first.",
        )

    target_channel = await _load_voice_channel(bot, guild, voice_channel_id)
    try:
        connected = await target_channel.connect()
    except discord.DiscordException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to voice channel {voice_channel_id}.",
        ) from exc

    if not isinstance(connected, discord.VoiceClient):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discord returned an unsupported voice client type.",
        )
    return connected


def create_api_app(
    bot: discord.Client,
    music: MusicManager,
    settings: Settings,
) -> FastAPI:
    app = FastAPI(title="Discord Music Bot Control API")

    async def require_api_key(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> None:
        if settings.api_token is None:
            return
        if x_api_key != settings.api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key.",
            )

    protected = APIRouter(dependencies=[Depends(require_api_key)])

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "discord_ready": bot.is_ready(),
            "guild_count": len(bot.guilds),
            "bot_user_id": bot.user.id if bot.user else None,
        }

    @protected.get("/guilds/{guild_id}/queue", response_model=QueueResponse)
    async def get_queue(guild_id: int) -> QueueResponse:
        _ensure_guild(bot, guild_id)
        state = music.get_state(guild_id)
        async with state.lock:
            now_playing = state.now_playing
            queue_copy = list(state.queue)

        return QueueResponse(
            guild_id=guild_id,
            volume_percent=music.get_volume_percent(guild_id),
            now_playing=_track_payload(now_playing) if now_playing else None,
            queue=[_track_payload(track) for track in queue_copy],
        )

    @protected.post("/guilds/{guild_id}/play")
    async def play(guild_id: int, payload: PlayRequest) -> dict[str, Any]:
        guild = _ensure_guild(bot, guild_id)
        vc = await _ensure_voice_connection(bot, guild, payload.voice_channel_id)

        track = await asyncio.to_thread(
            music.extract_track,
            payload.query,
            payload.requested_by,
        )

        state = music.get_state(guild_id)
        async with state.lock:
            state.queue.append(track)
            queue_length = len(state.queue)

        text_channel_id = payload.text_channel_id or _default_text_channel_id(guild)
        if not vc.is_playing() and not vc.is_paused():
            await music.play_next(guild_id, text_channel_id)

        return {
            "message": "Track queued.",
            "guild_id": guild_id,
            "queue_length": queue_length,
            "track": _track_payload(track).model_dump(),
        }

    @protected.post("/guilds/{guild_id}/pause")
    async def pause(guild_id: int) -> dict[str, str]:
        guild = _ensure_guild(bot, guild_id)
        vc = _connected_voice_client(guild)
        if vc is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bot is not connected to voice in this guild.",
            )
        if vc.is_paused():
            return {"message": "Playback is already paused."}
        if not vc.is_playing():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nothing is currently playing.",
            )
        vc.pause()
        return {"message": "Paused."}

    @protected.post("/guilds/{guild_id}/resume")
    async def resume(guild_id: int) -> dict[str, str]:
        guild = _ensure_guild(bot, guild_id)
        vc = _connected_voice_client(guild)
        if vc is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bot is not connected to voice in this guild.",
            )
        if vc.is_paused():
            vc.resume()
            return {"message": "Resumed."}
        if vc.is_playing():
            return {"message": "Playback is already running."}
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing is paused.",
        )

    @protected.post("/guilds/{guild_id}/skip")
    async def skip(guild_id: int) -> dict[str, str]:
        guild = _ensure_guild(bot, guild_id)
        vc = _connected_voice_client(guild)
        if vc is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bot is not connected to voice in this guild.",
            )
        if not vc.is_playing():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nothing is currently playing.",
            )
        vc.stop()
        return {"message": "Skipped."}

    @protected.post("/guilds/{guild_id}/stop")
    async def stop(guild_id: int) -> dict[str, str]:
        guild = _ensure_guild(bot, guild_id)

        state = music.get_state(guild_id)
        async with state.lock:
            state.queue.clear()
            state.now_playing = None

        vc = _connected_voice_client(guild)
        if vc is not None:
            vc.stop()

        return {"message": "Stopped and cleared the queue."}

    app.include_router(protected)
    return app
