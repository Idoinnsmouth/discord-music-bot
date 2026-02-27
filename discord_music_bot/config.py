import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None


def load_settings() -> Settings:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN env var first (your bot token).")

    guild_id: int | None = None
    guild_id_raw = os.environ.get("DISCORD_GUILD_ID")
    if guild_id_raw:
        try:
            guild_id = int(guild_id_raw)
        except ValueError as exc:
            raise RuntimeError("DISCORD_GUILD_ID must be an integer.") from exc

    return Settings(token=token, guild_id=guild_id)
