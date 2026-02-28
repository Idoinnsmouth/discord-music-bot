import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any, cast

import discord
import yt_dlp
from yt_dlp.utils import YoutubeDLError

logger = logging.getLogger(__name__)


def _detect_js_runtimes() -> dict[str, dict[str, str]] | None:
    runtimes: dict[str, dict[str, str]] = {}

    deno_path = os.environ.get("DENO_PATH") or shutil.which("deno")
    if not deno_path:
        for candidate in ("/opt/homebrew/bin/deno", "/usr/local/bin/deno"):
            if os.path.exists(candidate):
                deno_path = candidate
                break
    if deno_path:
        runtimes["deno"] = {"path": deno_path}

    node_path = os.environ.get("NODE_PATH") or shutil.which("node")
    if node_path:
        runtimes["node"] = {"path": node_path}

    return runtimes or None


YTDLP_OPTS: dict[str, Any] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "remote_components": ["ejs:github"],
    "js_runtimes": _detect_js_runtimes(),
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    requested_by: str


class GuildMusicState:
    def __init__(self) -> None:
        self.queue: list[Track] = []
        self.now_playing: Track | None = None
        self.volume: float = 1.0
        self.lock = asyncio.Lock()


class MusicManager:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self._states: dict[int, GuildMusicState] = {}

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def get_volume_percent(self, guild_id: int) -> int:
        state = self.get_state(guild_id)
        return int(round(state.volume * 100))

    def set_volume_percent(self, guild_id: int, percent: int) -> int:
        state = self.get_state(guild_id)
        clamped = max(0, min(200, percent))
        state.volume = clamped / 100
        return clamped

    def apply_volume_to_active(self, guild_id: int) -> bool:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False

        vc_protocol = guild.voice_client
        if not isinstance(vc_protocol, discord.VoiceClient):
            return False

        source = vc_protocol.source
        if isinstance(source, discord.PCMVolumeTransformer):
            state = self.get_state(guild_id)
            source.volume = state.volume
            return True

        return False

    @staticmethod
    def ensure_member(interaction: discord.Interaction) -> discord.Member:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            raise RuntimeError("Could not read your member state.")
        return interaction.user

    async def ensure_voice(self, interaction: discord.Interaction) -> discord.VoiceClient:
        if not interaction.guild:
            raise RuntimeError("This command only works in a server.")

        member = self.ensure_member(interaction)
        if not member.voice or not member.voice.channel:
            raise RuntimeError("You must be in a voice channel.")

        user_channel = member.voice.channel
        vc_protocol = interaction.guild.voice_client
        vc = vc_protocol if isinstance(vc_protocol, discord.VoiceClient) else None
        if vc and vc.is_connected():
            if vc.channel and vc.channel.id != user_channel.id:
                raise RuntimeError(
                    f"I'm already in **{vc.channel.name}**. Join that channel first."
                )
            return vc

        connected_vc = await user_channel.connect()
        if not isinstance(connected_vc, discord.VoiceClient):
            raise RuntimeError("Unsupported voice protocol implementation.")
        return connected_vc

    @staticmethod
    def extract_track(query: str, requester: str) -> Track:
        try:
            with yt_dlp.YoutubeDL(cast(Any, YTDLP_OPTS)) as ydl:
                info: Any = ydl.extract_info(query, download=False)
        except YoutubeDLError as exc:
            message = str(exc).lower()
            if (
                "javascript runtime" in message
                or "challenge" in message
                or "signature" in message
            ):
                raise RuntimeError(
                    "YouTube challenge solving failed. Ensure a JS runtime "
                    "(deno/node) is installed and accessible."
                ) from exc
            raise RuntimeError(
                "YouTube extraction failed for that query. Try another URL/search term."
            ) from exc
        except Exception as exc:
            raise RuntimeError("Unexpected error while talking to YouTube.") from exc

        if isinstance(info, dict) and "entries" in info:
            entries = info.get("entries")
            if not isinstance(entries, list):
                raise RuntimeError("Unexpected YouTube response shape.")
            info = next((entry for entry in entries if isinstance(entry, dict)), None)
            if info is None:
                raise RuntimeError("No playable result found for that query.")

        if not isinstance(info, dict):
            raise RuntimeError("Unexpected YouTube metadata shape.")

        title_value = info.get("title")
        title = title_value if isinstance(title_value, str) and title_value else "Unknown title"

        webpage_url_value = info.get("webpage_url")
        webpage_url = (
            webpage_url_value
            if isinstance(webpage_url_value, str) and webpage_url_value
            else query
        )

        stream_url_value = info.get("url")
        if not isinstance(stream_url_value, str) or not stream_url_value:
            raise RuntimeError("Could not extract an audio stream URL.")
        stream_url = stream_url_value

        return Track(
            title=title,
            webpage_url=webpage_url,
            stream_url=stream_url,
            requested_by=requester,
        )

    async def send_now_playing_message(self, text_channel_id: int | None, track: Track) -> None:
        if text_channel_id is None:
            return
        try:
            channel = self.bot.get_channel(text_channel_id)
            if not channel:
                fetched = await self.bot.fetch_channel(text_channel_id)
                if isinstance(fetched, discord.abc.Messageable):
                    channel = fetched

            if isinstance(channel, discord.abc.Messageable):
                await channel.send(
                    "Now playing: "
                    f"**{track.title}** (requested by {track.requested_by})\n"
                    f"{track.webpage_url}"
                )
        except discord.DiscordException as exc:
            logger.error(
                "Failed to post now-playing message for channel %s.",
                text_channel_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def _log_task_exception(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error:
            logger.error(
                "Background playback task failed.",
                exc_info=(type(error), error, error.__traceback__),
            )

    def _schedule_play_next(self, guild_id: int, text_channel_id: int | None) -> None:
        try:
            task = asyncio.create_task(self.play_next(guild_id, text_channel_id))
            task.add_done_callback(self._log_task_exception)
        except RuntimeError as exc:
            logger.error(
                "Failed to schedule next track playback.",
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    async def play_next(self, guild_id: int, text_channel_id: int | None) -> None:
        state = self.get_state(guild_id)
        try:
            guild = self.bot.get_guild(guild_id)

            if not guild or not guild.voice_client:
                state.now_playing = None
                return

            vc_protocol = guild.voice_client
            vc = vc_protocol if isinstance(vc_protocol, discord.VoiceClient) else None
            if not vc:
                state.now_playing = None
                return
            async with state.lock:
                if vc.is_playing() or vc.is_paused():
                    return
                if not state.queue:
                    state.now_playing = None
                    return
                track = state.queue.pop(0)
                state.now_playing = track

            try:
                source = discord.FFmpegPCMAudio(
                    track.stream_url,
                    before_options=FFMPEG_BEFORE_OPTS,
                    options=FFMPEG_OPTS,
                )
                volume_source = discord.PCMVolumeTransformer(source, volume=state.volume)
            except Exception as exc:
                logger.error(
                    "Failed to create ffmpeg source for '%s'.",
                    track.title,
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                self._schedule_play_next(guild_id, text_channel_id)
                return

            def after_play(err: Exception | None) -> None:
                if err:
                    logger.error(
                        "Playback error (guild=%s).",
                        guild_id,
                        exc_info=(type(err), err, err.__traceback__),
                    )
                self.bot.loop.call_soon_threadsafe(
                    self._schedule_play_next,
                    guild_id,
                    text_channel_id,
                )

            try:
                vc.play(volume_source, after=after_play)
            except Exception as exc:
                logger.error(
                    "Discord voice client failed to start playback.",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                self._schedule_play_next(guild_id, text_channel_id)
                return

            await self.send_now_playing_message(text_channel_id, track)
        except Exception as exc:
            state.now_playing = None
            logger.error(
                "Unexpected error in play_next.",
                exc_info=(type(exc), exc, exc.__traceback__),
            )
