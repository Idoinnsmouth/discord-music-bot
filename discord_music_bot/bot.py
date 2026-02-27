import asyncio
import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings, load_settings
from .music import MusicManager

logger = logging.getLogger(__name__)


def create_bot(settings: Settings) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    music = MusicManager(bot)

    def log_error(message: str, error: Exception) -> None:
        logger.error(message, exc_info=(type(error), error, error.__traceback__))

    async def safe_interaction_reply(
        interaction: discord.Interaction,
        message: str,
        *,
        ephemeral: bool = True,
    ) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(message, ephemeral=ephemeral)
        except discord.DiscordException as send_error:
            log_error("Failed to send interaction response.", send_error)

    def asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        error = context.get("exception")
        msg = context.get("message", "Unhandled asyncio exception.")
        if isinstance(error, Exception):
            log_error(msg, error)
        else:
            logger.error("%s Context=%s", msg, context)

    @bot.event
    async def on_ready() -> None:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(asyncio_exception_handler)

        user = bot.user
        if user is None:
            logger.warning("on_ready fired but bot.user is None.")
            return

        print(f"Logged in as {user} (ID: {user.id})")
        guilds = ", ".join(f"{guild.name} ({guild.id})" for guild in bot.guilds) or "none"
        print(f"Connected guilds: {guilds}")
        try:
            if settings.guild_id:
                guild_obj = discord.Object(id=settings.guild_id)
                if not bot.get_guild(settings.guild_id):
                    print(
                        f"Warning: DISCORD_GUILD_ID={settings.guild_id} "
                        "is not in connected guilds. "
                        "Commands may not appear in your intended server."
                    )
                # Copy global commands into the target guild for near-instant propagation.
                bot.tree.copy_global_to(guild=guild_obj)
                synced = await bot.tree.sync(guild=guild_obj)
                print(f"Synced {len(synced)} command(s) to guild {settings.guild_id}.")
            else:
                synced = await bot.tree.sync()
                print(f"Synced {len(synced)} global command(s).")
        except Exception as e:
            print("Command sync failed:", e)

    @bot.event
    async def on_error(event_method: str, *args: Any, **kwargs: Any) -> None:
        logger.exception("Unhandled Discord event error in %s.", event_method)

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        unwrapped = error
        if isinstance(error, app_commands.CommandInvokeError) and error.original:
            unwrapped = error.original

        if isinstance(unwrapped, app_commands.CheckFailure):
            await safe_interaction_reply(interaction, "You can't use this command here.")
            return

        if isinstance(unwrapped, app_commands.CommandOnCooldown):
            await safe_interaction_reply(
                interaction,
                f"That command is on cooldown. Try again in {unwrapped.retry_after:.1f}s.",
            )
            return

        if isinstance(unwrapped, Exception):
            log_error("Unhandled slash-command exception.", unwrapped)
        else:
            logger.error("Unhandled non-exception slash-command error: %r", unwrapped)

        await safe_interaction_reply(
            interaction,
            "Something went wrong while processing that command.",
        )

    @bot.tree.command(name="join", description="Join your current voice channel")
    @app_commands.guild_only()
    async def join(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            await music.ensure_voice(interaction)
            await interaction.followup.send("Joined your voice channel.")
        except Exception as e:
            await safe_interaction_reply(interaction, str(e))

    @bot.tree.command(name="play", description="Play a YouTube URL or search query")
    @app_commands.guild_only()
    @app_commands.describe(query="YouTube URL or search terms")
    async def play(interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(thinking=True)
        if not interaction.guild or not interaction.channel:
            await interaction.followup.send("This command only works in a server.")
            return

        state = music.get_state(interaction.guild.id)

        try:
            vc = await music.ensure_voice(interaction)
            member = music.ensure_member(interaction)
            track = await asyncio.to_thread(
                music.extract_track,
                query,
                member.display_name,
            )

            async with state.lock:
                state.queue.append(track)

            await interaction.followup.send(
                f"Added to queue: **{track.title}**\n{track.webpage_url}"
            )

            if not vc.is_playing() and not vc.is_paused():
                await music.play_next(interaction.guild.id, interaction.channel.id)
        except Exception as e:
            await safe_interaction_reply(interaction, str(e))

    @bot.tree.command(name="pause", description="Pause the current track")
    @app_commands.guild_only()
    async def pause(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        vc_protocol = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(vc_protocol, discord.VoiceClient):
            await interaction.followup.send("I'm not connected.")
            return
        vc = vc_protocol
        if not vc.is_connected():
            await interaction.followup.send("I'm not connected.")
            return
        if vc.is_paused():
            await interaction.followup.send("Playback is already paused.")
            return
        if not vc.is_playing():
            await interaction.followup.send("Nothing is playing.")
            return

        vc.pause()
        await interaction.followup.send("Paused.")

    @bot.tree.command(name="resume", description="Resume playback")
    @app_commands.guild_only()
    async def resume(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        vc_protocol = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(vc_protocol, discord.VoiceClient):
            await interaction.followup.send("I'm not connected.")
            return
        vc = vc_protocol
        if not vc.is_connected():
            await interaction.followup.send("I'm not connected.")
            return
        if vc.is_paused():
            vc.resume()
            await interaction.followup.send("Resumed.")
            return
        if vc.is_playing():
            await interaction.followup.send("Playback is already running.")
            return
        await interaction.followup.send("Nothing is paused.")

    @bot.tree.command(name="skip", description="Skip the current track")
    @app_commands.guild_only()
    async def skip(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        vc_protocol = interaction.guild.voice_client if interaction.guild else None
        if not isinstance(vc_protocol, discord.VoiceClient):
            await interaction.followup.send("I'm not connected.")
            return
        vc = vc_protocol
        if not vc.is_connected():
            await interaction.followup.send("I'm not connected.")
            return
        if not vc.is_playing():
            await interaction.followup.send("Nothing is playing.")
            return
        vc.stop()
        await interaction.followup.send("Skipped.")

    @bot.tree.command(name="volume", description="Set playback volume (0-200%)")
    @app_commands.guild_only()
    @app_commands.describe(percent="Volume percent, from 0 to 200")
    async def volume(interaction: discord.Interaction, percent: int) -> None:
        await interaction.response.defer(thinking=True)
        if not interaction.guild:
            await interaction.followup.send("Server only.")
            return
        if percent < 0 or percent > 200:
            await interaction.followup.send("Volume must be between 0 and 200.")
            return

        applied_percent = music.set_volume_percent(interaction.guild.id, percent)
        applied_to_active = music.apply_volume_to_active(interaction.guild.id)
        suffix = (
            "Applied to the currently playing track."
            if applied_to_active
            else "Will apply from the next track."
        )
        await interaction.followup.send(f"Volume set to **{applied_percent}%**. {suffix}")

    @bot.tree.command(name="stop", description="Stop playback and clear the queue")
    @app_commands.guild_only()
    async def stop(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not interaction.guild:
            await interaction.followup.send("Server only.")
            return
        state = music.get_state(interaction.guild.id)
        async with state.lock:
            state.queue.clear()
            state.now_playing = None

        vc_protocol = interaction.guild.voice_client
        if isinstance(vc_protocol, discord.VoiceClient) and vc_protocol.is_connected():
            vc = vc_protocol
            vc.stop()
        await interaction.followup.send("Stopped and cleared the queue.")

    @bot.tree.command(name="leave", description="Disconnect from voice")
    @app_commands.guild_only()
    async def leave(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not interaction.guild:
            await interaction.followup.send("Server only.")
            return

        state = music.get_state(interaction.guild.id)
        async with state.lock:
            state.queue.clear()
            state.now_playing = None

        vc_protocol = interaction.guild.voice_client
        if isinstance(vc_protocol, discord.VoiceClient) and vc_protocol.is_connected():
            vc = vc_protocol
            await vc.disconnect()
            await interaction.followup.send("Disconnected.")
            return

        await interaction.followup.send("I'm not connected.")

    @bot.tree.command(name="queue", description="Show the current queue")
    @app_commands.guild_only()
    async def queue(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        if not interaction.guild:
            await interaction.followup.send("Server only.")
            return

        state = music.get_state(interaction.guild.id)

        lines = []
        lines.append(f"Volume: {music.get_volume_percent(interaction.guild.id)}%")
        if state.now_playing:
            lines.append(f"Now: {state.now_playing.title}")
        if state.queue:
            lines.extend(f"{idx + 1}. {track.title}" for idx, track in enumerate(state.queue[:10]))

        if not lines:
            await interaction.followup.send("Queue is empty.")
            return

        more = "" if len(state.queue) <= 10 else f"\n...and {len(state.queue) - 10} more."
        await interaction.followup.send("Queue:\n" + "\n".join(lines) + more)

    return bot


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    bot = create_bot(settings)
    bot.run(settings.token)


if __name__ == "__main__":
    main()
