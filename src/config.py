"""
CryptoBot Studio - Configuration Management
Pydantic Settings for Upbit Auto Trading Bot
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Literal


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
    
    # Upbit API
    upbit_access_key: str
    upbit_secret_key: str
    
    @field_validator('telegram_bot_token', 'telegram_chat_id', 'upbit_access_key', 'upbit_secret_key', mode='before')
    @classmethod
    def strip_whitespace(cls, v):
        """Remove whitespace and newlines from sensitive values"""
        if isinstance(v, str):
            return v.strip()
        return v
    
    # Trading Settings
    trade_symbol: str = "KRW-BTC"
    trade_amount: float = 10000  # KRW
    

    
    # Bollinger Bands Settings (legacy)
    bb_period: int = 20
    bb_std: float = 2.0
    
    # Orderbook Scalping Settings
    scalping_bid_ask_ratio: float = 2.0   # 매수/매도 비율 임계값
    scalping_take_profit: float = 0.35    # 익절 % (수수료 0.1% 고려)
    scalping_stop_loss: float = 0.5       # 손절 %
    
    # Risk Management
    max_daily_trades: int = 100  # 스캘핑은 고빈도
    max_daily_loss: float = 50000  # KRW
    
    # Bot Mode
    bot_mode: Literal["semi", "full"] = "semi"
    
    # Timezone
    timezone: str = "Asia/Seoul"
    
    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = Settings()
