"""
CryptoBot Studio - Market Analyzer
시장 상황 감지 시스템 (변동성/추세 레짐)

Karpathy의 원칙:
"시장을 먼저 이해하고, 그에 맞는 전략을 선택하라."
"""
import pandas as pd
import numpy as np
from typing import Literal, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class VolatilityRegime(Enum):
    """변동성 레짐"""
    LOW = "LOW"         # ATR 하위 25%
    MEDIUM = "MEDIUM"   # ATR 중간 50%
    HIGH = "HIGH"       # ATR 상위 25%


class TrendRegime(Enum):
    """추세 레짐"""
    STRONG_UP = "STRONG_UP"     # ADX 25+ & +DI > -DI
    WEAK_UP = "WEAK_UP"         # 상승 but ADX < 25
    RANGING = "RANGING"         # ADX < 20
    WEAK_DOWN = "WEAK_DOWN"     # 하락 but ADX < 25
    STRONG_DOWN = "STRONG_DOWN" # ADX 25+ & -DI > +DI


@dataclass
class MarketState:
    """시장 상태"""
    volatility: VolatilityRegime
    trend: TrendRegime
    atr: float
    atr_percent: float  # ATR / 현재가 (%)
    adx: float
    rsi: float
    recommended_strategy: str
    position_size_multiplier: float
    
    def __str__(self):
        vol_emoji = "🟢" if self.volatility == VolatilityRegime.LOW else "🟡" if self.volatility == VolatilityRegime.MEDIUM else "🔴"
        trend_emoji = "📈" if "UP" in self.trend.value else "📉" if "DOWN" in self.trend.value else "➡️"
        
        return (
            f"{vol_emoji} 변동성: {self.volatility.value} (ATR: {self.atr_percent:.2f}%)\n"
            f"{trend_emoji} 추세: {self.trend.value} (ADX: {self.adx:.1f})\n"
            f"📊 RSI: {self.rsi:.1f}\n"
            f"🎯 추천 전략: {self.recommended_strategy}\n"
            f"📏 포지션 배수: {self.position_size_multiplier:.1f}x"
        )


class MarketAnalyzer:
    """
    시장 분석기
    
    기능:
    1. ATR 기반 변동성 레짐 감지
    2. ADX 기반 추세 강도 분석
    3. 시장 상황에 맞는 전략 추천
    4. 동적 포지션 사이징
    """
    
    def __init__(
        self,
        atr_period: int = 14,
        adx_period: int = 14,
        lookback_for_percentile: int = 100
    ):
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.lookback = lookback_for_percentile
    
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Average True Range 계산"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        return atr
    
    def calculate_adx(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        ADX (Average Directional Index) 계산
        
        Returns:
            (ADX, +DI, -DI)
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # +DM, -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        # Smoothed values
        atr = tr.rolling(window=self.adx_period).mean()
        plus_di = 100 * (plus_dm.rolling(window=self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=self.adx_period).mean() / atr)
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=self.adx_period).mean()
        
        return adx, plus_di, minus_di
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_volatility_regime(self, current_atr_pct: float, historical_atr_pcts: pd.Series) -> VolatilityRegime:
        """변동성 레짐 결정"""
        if len(historical_atr_pcts) < 10:
            return VolatilityRegime.MEDIUM
        
        p25 = historical_atr_pcts.quantile(0.25)
        p75 = historical_atr_pcts.quantile(0.75)
        
        if current_atr_pct <= p25:
            return VolatilityRegime.LOW
        elif current_atr_pct >= p75:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.MEDIUM
    
    def get_trend_regime(self, adx: float, plus_di: float, minus_di: float) -> TrendRegime:
        """추세 레짐 결정"""
        if np.isnan(adx) or np.isnan(plus_di) or np.isnan(minus_di):
            return TrendRegime.RANGING
        
        is_uptrend = plus_di > minus_di
        
        if adx < 20:
            return TrendRegime.RANGING
        elif adx >= 25:
            return TrendRegime.STRONG_UP if is_uptrend else TrendRegime.STRONG_DOWN
        else:
            return TrendRegime.WEAK_UP if is_uptrend else TrendRegime.WEAK_DOWN
    
    def get_recommended_strategy(
        self,
        volatility: VolatilityRegime,
        trend: TrendRegime,
        rsi: float
    ) -> Tuple[str, float]:
        """
        시장 상황에 맞는 전략 추천
        
        목표: 70%+ 승률 (안정성 우선)
        
        Returns:
            (전략명, 포지션 배수)
        """
        # 고변동성 시장 → 보수적
        if volatility == VolatilityRegime.HIGH:
            if trend in [TrendRegime.STRONG_UP, TrendRegime.STRONG_DOWN]:
                return "CONSERVATIVE_TREND", 0.5  # 추세는 따르되 작게
            else:
                return "SKIP", 0.0  # 고변동 횡보는 위험
        
        # 저변동성 시장 → 적극적
        if volatility == VolatilityRegime.LOW:
            if trend == TrendRegime.RANGING:
                return "ICT_MEAN_REVERSION", 1.0  # 레인징에서 ICT 강점
            elif trend in [TrendRegime.STRONG_UP, TrendRegime.WEAK_UP]:
                return "TREND_FOLLOWING", 1.2  # 안정적 상승 추세
            else:
                return "SKIP", 0.0  # 저변동 하락 조심
        
        # 중변동성 시장
        if trend == TrendRegime.STRONG_UP:
            if rsi < 60:  # 과매수 아닌 상승
                return "ICT_CONFLUENCE", 1.0
            else:
                return "CONSERVATIVE_TREND", 0.7
        
        if trend == TrendRegime.RANGING:
            if 40 < rsi < 60:
                return "ICT_MEAN_REVERSION", 0.8
            else:
                return "SKIP", 0.0
        
        # 하락 추세는 보수적
        if trend in [TrendRegime.WEAK_DOWN, TrendRegime.STRONG_DOWN]:
            return "SKIP", 0.0
        
        return "ICT_CONFLUENCE", 0.7  # 기본값
    
    def analyze(self, df: pd.DataFrame) -> Optional[MarketState]:
        """
        시장 분석 실행
        
        Args:
            df: OHLCV DataFrame (최소 100개 캔들 권장)
            
        Returns:
            MarketState
        """
        if df is None or len(df) < 50:
            logger.warning("데이터 부족으로 시장 분석 불가")
            return None
        
        # 지표 계산
        atr = self.calculate_atr(df)
        adx, plus_di, minus_di = self.calculate_adx(df)
        rsi = self.calculate_rsi(df)
        
        current_price = df['close'].iloc[-1]
        current_atr = atr.iloc[-1]
        current_atr_pct = (current_atr / current_price) * 100
        
        # ATR % 히스토리
        atr_pct_history = (atr / df['close']) * 100
        
        # 레짐 결정
        volatility = self.get_volatility_regime(current_atr_pct, atr_pct_history.tail(self.lookback))
        trend = self.get_trend_regime(
            adx.iloc[-1],
            plus_di.iloc[-1],
            minus_di.iloc[-1]
        )
        
        # 전략 추천
        strategy, size_mult = self.get_recommended_strategy(
            volatility, trend, rsi.iloc[-1]
        )
        
        return MarketState(
            volatility=volatility,
            trend=trend,
            atr=current_atr,
            atr_percent=current_atr_pct,
            adx=adx.iloc[-1] if not np.isnan(adx.iloc[-1]) else 0,
            rsi=rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50,
            recommended_strategy=strategy,
            position_size_multiplier=size_mult
        )


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== Market Analyzer Test ===\n")
    
    symbols = ["KRW-ETH", "KRW-SOL", "KRW-XRP"]
    analyzer = MarketAnalyzer()
    
    for symbol in symbols:
        print(f"\n📌 {symbol}")
        print("-" * 40)
        
        df = pyupbit.get_ohlcv(symbol, interval="minute60", count=100)
        
        if df is not None:
            state = analyzer.analyze(df)
            if state:
                print(state)
        else:
            print("❌ 데이터 조회 실패")
