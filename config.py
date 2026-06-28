from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    bot_token: str = Field(..., env='BOT_TOKEN')
    owner_id: int = Field(..., env='OWNER_ID')
    mongodb_uri: str = Field(..., env='MONGODB_URI')
    database_channel_id: int = Field(..., env='DATABASE_CHANNEL_ID')
    debug: bool = Field(True, env='DEBUG')
    log_level: str = Field('INFO', env='LOG_LEVEL')

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

config = Settings()
