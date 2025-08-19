import discord
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Discord bot configuration settings."""
    
    DISCORD_TOKEN: str
    COMMAND_PREFIX: str = "!"
    DEBUG: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    
    @property
    def get_intents(self) -> discord.Intents:
        """Configure Discord intents for message reading and server access."""
        intents = discord.Intents.default()
        intents.message_content = True    # For reading message content
        intents.guilds = True             # For server information  
        intents.guild_messages = True     # For message events
        intents.members = True            # For member information
        return intents


# Instantiated object for import
settings = BotSettings()