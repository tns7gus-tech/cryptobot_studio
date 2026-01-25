"""
CryptoBot Studio - Configuration Management
Pydantic Settings for Upbit Auto Trading Bot
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Literal, List


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
    
    # Proxy Settings (Static IP Support)
    # Railway 등에서 고정 IP를 위해 사용 (예: Quotaguard Static)
    # 포맷: http://user:pass@host:port
    proxy_url: Optional[str] = None
    
    @field_validator('proxy_url', mode='before')
    @classmethod
    def check_proxy_aliases(cls, v, info):
        """
        PROXY_URL이 없으면 QUOTAGUARDSTATIC_URL 등을 확인
        """
        if v:
            return v
            
        # Pydantic v2에서는 info.data 사용 안함, 환경변수 직접 조회는 여기서 어려움
        # 따라서 메인 로직이나 Dockerfile에서 매핑하는 것이 좋으나,
        # 편의상 여기서는 None으로 두고 외부에서 PROXY_URL로 통일해서 주입 권장
        return v
    
    # Exclude Symbols (봇이 건드리지 않을 코인 목록)
    # 장기 보유 목적의 코인은 여기에 추가 (예: "KRW-BTC,KRW-ETH,KRW-CRO")
    exclude_symbols: List[str] = []
    
    @field_validator('exclude_symbols', mode='before')
    @classmethod
    def parse_exclude_symbols(cls, v):
        """
        문자열로 입력된 경우 쉼표로 분리하여 리스트로 변환
        """
        if isinstance(v, str):
            if not v.strip():
                return []
            return [s.strip().upper() for s in v.split(',')]
        return v or []


# Global settings instance
settings = Settings()
