"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )
    
    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str
    
    # Google AI
    google_ai_api_key: str
    
    # Polymarket (for full auto mode)
    polymarket_private_key: Optional[str] = None
    polymarket_funder_address: Optional[str] = None
    
    # Bot settings
    bot_mode: str = "semi"  # semi or full
    whale_threshold: int = 10000  # $10,000
    max_bet_amount: int = 50  # $50
    max_daily_bets: int = 5
    max_daily_loss: int = 200  # $200
    
    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = Settings()

