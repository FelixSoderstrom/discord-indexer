import discord
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Discord bot configuration settings.

    Manages environment-based configuration for Discord bot including
    token management, command prefix, debug settings, Discord intents,
    voice channel features, and speech-to-text (STT) capabilities.
    """

    DISCORD_TOKEN: str
    COMMAND_PREFIX: str = "!"
    DEBUG: bool = False
    TEXT_MODEL_NAME: str
    VISION_MODEL_NAME: str
    LANGCHAIN_VERBOSE: bool = False
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Voice channel features
    ENABLE_VOICE_FEATURES: bool = False
    VOICE_TIMEOUT: int = 60

    # Speech-to-Text configuration
    ENABLE_STT: bool = False
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "int8"
    STT_SILENCE_DURATION_MS: int = 500
    STT_CACHE_DIR: str = "cache/transcriptions"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    
    @property
    def LLM_MODEL_NAME(self) -> str:
        """Backward compatibility property for TEXT_MODEL_NAME.
        
        Returns:
            The text model name (same as TEXT_MODEL_NAME)
        """
        return self.TEXT_MODEL_NAME
    
    @property
    def get_intents(self) -> discord.Intents:
        """Configure Discord intents for message reading and server access.

        Returns:
            Discord.Intents object configured for message content, guild access,
            message events, member information, and optionally voice states.
        """
        intents = discord.Intents.default()
        intents.message_content = True    # For reading message content
        intents.guilds = True             # For server information
        intents.guild_messages = True     # For message events
        intents.members = True            # For member information

        # Enable voice state tracking if voice features are enabled
        if self.ENABLE_VOICE_FEATURES:
            intents.voice_states = True   # For voice channel events

        return intents


# Instantiated object for import
settings = BotSettings()