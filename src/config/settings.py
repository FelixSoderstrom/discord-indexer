import discord
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Discord bot configuration settings.
    
    Manages environment-based configuration for Discord bot including
    token management, command prefix, debug settings, and Discord intents.
    """
    
    DISCORD_TOKEN: str
    COMMAND_PREFIX: str = "!"
    DEBUG: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    
    @property
    def get_intents(self) -> discord.Intents:
        """Configure Discord intents for message reading, server access, and voice functionality.
        
        Returns:
            Discord.Intents object configured for message content, guild access,
            message events, member information, and voice state monitoring.
        """
        intents = discord.Intents.default()
        intents.message_content = True    # For reading message content
        intents.guilds = True             # For server information  
        intents.guild_messages = True     # For message events
        intents.members = True            # For member information
        intents.voice_states = True       # For voice channel monitoring
        return intents


# Instantiated object for import
settings = BotSettings()