"""
CryptoBot Studio - Trend Following Analyzer
RSI + EMA 기반 추세 추종 스캘핑 전략
5분봉 고빈도 거래로 일일 목표 달성 보조
"""
import pandas as pd
from typing import Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class TrendSignal:
    """추세 추종 신호"""
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 ~ 1.0
    reason: str
    rsi: float
    ema_fast: float
    ema_slow: float
    entry_price: float
    
    def __str__(self):
        emoji = "🟢" if self.action == "BUY" else "🔴" if self.action == "SELL" else "⏸️"
        return f"{emoji} TREND {self.action}: RSI={self.rsi:.1f}, EMA Fast={'>' if self.ema_fast > self.ema_slow else '<'}Slow [{self.confidence:.0%}]"


class TrendFollowingAnalyzer:
    """
    추세 추종 분석기 (고빈도 스캘핑)
    
    전략:
    - BUY: EMA 골든크로스 + RSI < 50 (상승 초입)
    - SELL: EMA 데드크로스 + RSI > 50 (하락 초입)
    
    특징:
    - 5분봉 기준
    - 빠른 익절 (0.3%)
    - 빠른 손절 (0.5%)
    - 타임아웃 (5분)
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        ema_fast: int = 12,
        ema_slow: int = 26,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        take_profit: float = 0.3,
        stop_loss: float = 0.5
    ):
        self.rsi_period = rsi_period
        self.ema_fast_period = ema_fast
        self.ema_slow_period = ema_slow
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.take_profit = take_profit
        self.stop_loss = stop_loss
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """EMA 계산"""
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def analyze(
        self,
        df: pd.DataFrame,
        current_price: float = None,
        in_position: bool = False,
        entry_price: float = None
    ) -> TrendSignal:
        """
        추세 분석 수행
        
        Args:
            df: OHLCV DataFrame (5분봉 권장)
            current_price: 현재가
            in_position: 포지션 보유 여부
            entry_price: 진입가
            
        Returns:
            TrendSignal
        """
        min_length = max(self.rsi_period, self.ema_slow_period) + 5
        
        if df is None or len(df) < min_length:
            return TrendSignal(
                action="HOLD",
                confidence=0.0,
                reason="데이터 부족",
                rsi=50,
                ema_fast=0,
                ema_slow=0,
                entry_price=0
            )
        
        # 지표 계산
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df, self.rsi_period)
        df['ema_fast'] = self.calculate_ema(df, self.ema_fast_period)
        df['ema_slow'] = self.calculate_ema(df, self.ema_slow_period)
        
        current_price = current_price or df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        ema_fast = df['ema_fast'].iloc[-1]
        ema_slow = df['ema_slow'].iloc[-1]
        
        # 이전 값 (크로스 확인용)
        prev_ema_fast = df['ema_fast'].iloc[-2]
        prev_ema_slow = df['ema_slow'].iloc[-2]
        
        # 포지션 보유 중 - 익절/손절 판단
        if in_position and entry_price and entry_price > 0:
            profit_rate = ((current_price - entry_price) / entry_price) * 100
            
            if profit_rate >= self.take_profit:
                return TrendSignal(
                    action="SELL",
                    confidence=0.95,
                    reason=f"익절: +{profit_rate:.2f}%",
                    rsi=current_rsi,
                    ema_fast=ema_fast,
                    ema_slow=ema_slow,
                    entry_price=current_price
                )
            
            if profit_rate <= -self.stop_loss:
                return TrendSignal(
                    action="SELL",
                    confidence=0.95,
                    reason=f"손절: {profit_rate:.2f}%",
                    rsi=current_rsi,
                    ema_fast=ema_fast,
                    ema_slow=ema_slow,
                    entry_price=current_price
                )
        
        # 골든크로스 + 저 RSI = BUY
        golden_cross = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
        bullish_rsi = current_rsi < 50 and current_rsi > self.rsi_oversold
        
        if golden_cross or (ema_fast > ema_slow and bullish_rsi):
            confidence = 0.7 + (50 - current_rsi) / 100  # RSI 낮을수록 높은 신뢰도
            return TrendSignal(
                action="BUY",
                confidence=min(0.9, confidence),
                reason=f"{'골든크로스' if golden_cross else 'EMA 정배열'} + RSI {current_rsi:.1f}",
                rsi=current_rsi,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                entry_price=current_price
            )
        
        # 데드크로스 + 고 RSI = SELL (공매도 불가하므로 보유 시만)
        dead_cross = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
        bearish_rsi = current_rsi > 50 and current_rsi < self.rsi_overbought
        
        if in_position and (dead_cross or (ema_fast < ema_slow and bearish_rsi)):
            return TrendSignal(
                action="SELL",
                confidence=0.7,
                reason=f"{'데드크로스' if dead_cross else 'EMA 역배열'} + RSI {current_rsi:.1f}",
                rsi=current_rsi,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                entry_price=current_price
            )
        
        # HOLD
        return TrendSignal(
            action="HOLD",
            confidence=0.3,
            reason=f"신호 없음 (RSI: {current_rsi:.1f})",
            rsi=current_rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            entry_price=current_price
        )


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== Trend Following Analyzer Test ===\n")
    
    # ETH 5분봉 테스트
    symbol = "KRW-ETH"
    df = pyupbit.get_ohlcv(symbol, interval="minute5", count=50)
    
    if df is not None:
        current_price = pyupbit.get_current_price(symbol)
        print(f"📌 {symbol} 현재가: ₩{current_price:,.0f}\n")
        
        analyzer = TrendFollowingAnalyzer()
        signal = analyzer.analyze(df, current_price)
        
        print(f"📊 신호: {signal}")
        print(f"   RSI: {signal.rsi:.1f}")
        print(f"   EMA Fast: ₩{signal.ema_fast:,.0f}")
        print(f"   EMA Slow: ₩{signal.ema_slow:,.0f}")
    else:
        print("❌ 데이터 조회 실패")
