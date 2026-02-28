import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
    api_host: str
    api_port: int
    api_token: str | None


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

    api_host = os.environ.get("CONTROL_API_HOST", "0.0.0.0")

    api_port_raw = os.environ.get("CONTROL_API_PORT", "8000")
    try:
        api_port = int(api_port_raw)
    except ValueError as exc:
        raise RuntimeError("CONTROL_API_PORT must be an integer.") from exc

    api_token = os.environ.get("CONTROL_API_TOKEN")
    if api_token == "":
        api_token = None

    return Settings(
        token=token,
        guild_id=guild_id,
        api_host=api_host,
        api_port=api_port,
        api_token=api_token,
    )
