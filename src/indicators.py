"""
CryptoBot Studio - Technical Indicators
RSI, Bollinger Bands, and other technical analysis functions
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class RSIResult:
    """RSI 계산 결과"""
    value: float
    is_oversold: bool  # 과매도 (매수 신호)
    is_overbought: bool  # 과매수 (매도 신호)
    
    def __str__(self):
        status = "과매도" if self.is_oversold else "과매수" if self.is_overbought else "중립"
        return f"RSI: {self.value:.2f} ({status})"


@dataclass
class BollingerBandsResult:
    """볼린저밴드 계산 결과"""
    upper: float  # 상단 밴드
    middle: float  # 중간 (이동평균)
    lower: float  # 하단 밴드
    current_price: float
    is_above_upper: bool  # 상단 돌파 (매도 신호)
    is_below_lower: bool  # 하단 돌파 (매수 신호)
    percent_b: float  # %B 지표 (0 = 하단, 1 = 상단)
    
    def __str__(self):
        status = "상단돌파" if self.is_above_upper else "하단돌파" if self.is_below_lower else "밴드내"
        return f"BB: {self.current_price:,.0f} ({status}) [L:{self.lower:,.0f} M:{self.middle:,.0f} U:{self.upper:,.0f}]"


@dataclass
class FVGResult:
    """ICT Fair Value Gap 탐지 결과"""
    found: bool
    direction: str  # "BULLISH" or "BEARISH" or "NONE"
    gap_top: float  # FVG 상단 (상승 시 candle[N].low)
    gap_bottom: float  # FVG 하단 (상승 시 candle[N-2].high)
    stop_loss: float  # 손절가 (candle[N-1].low for BULLISH)
    take_profit: float  # 목표가 (candle[N-1].high for BULLISH)
    momentum_candle_time: Optional[str]  # 모멘텀 캔들 시간
    gap_size: float  # 갭 크기 (원화)
    gap_percent: float  # 갭 크기 (%)
    
    def __str__(self):
        if not self.found:
            return "FVG: 미발견"
        emoji = "🟢" if self.direction == "BULLISH" else "🔴"
        return f"{emoji} FVG({self.direction}): 갭 ₩{self.gap_bottom:,.0f}~₩{self.gap_top:,.0f} ({self.gap_percent:.2f}%), SL: ₩{self.stop_loss:,.0f}"


def calculate_rsi(
    prices: pd.Series,
    period: int = 14,
    buy_threshold: int = 30,
    sell_threshold: int = 70
) -> Optional[RSIResult]:
    """
    RSI (Relative Strength Index) 계산
    
    Args:
        prices: 종가 시리즈
        period: RSI 기간 (기본 14)
        buy_threshold: 과매도 기준 (기본 30)
        sell_threshold: 과매수 기준 (기본 70)
        
    Returns:
        RSIResult or None
    """
    if prices is None or len(prices) < period + 1:
        logger.warning(f"RSI 계산 불가: 데이터 부족 (필요: {period + 1}, 현재: {len(prices) if prices is not None else 0})")
        return None
    
    try:
        # 가격 변화량
        delta = prices.diff()
        
        # 상승/하락 분리
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        
        # 평균 상승/하락 (Wilder's smoothing)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        # RS 계산
        rs = avg_gain / avg_loss
        rs = rs.replace([np.inf, -np.inf], 0)
        
        # RSI 계산
        rsi = 100 - (100 / (1 + rs))
        
        # 마지막 값
        current_rsi = float(rsi.iloc[-1])
        
        return RSIResult(
            value=current_rsi,
            is_oversold=current_rsi < buy_threshold,
            is_overbought=current_rsi > sell_threshold
        )
        
    except Exception as e:
        logger.error(f"RSI 계산 에러: {e}")
        return None


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> Optional[BollingerBandsResult]:
    """
    볼린저 밴드 계산
    
    Args:
        prices: 종가 시리즈
        period: 이동평균 기간 (기본 20)
        std_dev: 표준편차 배수 (기본 2.0)
        
    Returns:
        BollingerBandsResult or None
    """
    if prices is None or len(prices) < period:
        logger.warning(f"BB 계산 불가: 데이터 부족 (필요: {period}, 현재: {len(prices) if prices is not None else 0})")
        return None
    
    try:
        # 이동평균 (중간선)
        middle = prices.rolling(window=period).mean()
        
        # 표준편차
        std = prices.rolling(window=period).std()
        
        # 상단/하단 밴드
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        # 마지막 값들
        current_price = float(prices.iloc[-1])
        current_upper = float(upper.iloc[-1])
        current_middle = float(middle.iloc[-1])
        current_lower = float(lower.iloc[-1])
        
        # %B 계산 (현재 가격이 밴드 내 어디에 위치하는지)
        band_width = current_upper - current_lower
        percent_b = (current_price - current_lower) / band_width if band_width > 0 else 0.5
        
        return BollingerBandsResult(
            upper=current_upper,
            middle=current_middle,
            lower=current_lower,
            current_price=current_price,
            is_above_upper=current_price > current_upper,
            is_below_lower=current_price < current_lower,
            percent_b=percent_b
        )
        
    except Exception as e:
        logger.error(f"볼린저밴드 계산 에러: {e}")
        return None


def calculate_sma(prices: pd.Series, period: int) -> Optional[float]:
    """
    단순 이동평균 (SMA) 계산
    
    Args:
        prices: 가격 시리즈
        period: 이동평균 기간
        
    Returns:
        SMA 값
    """
    if prices is None or len(prices) < period:
        return None
    
    try:
        return float(prices.rolling(window=period).mean().iloc[-1])
    except Exception as e:
        logger.error(f"SMA 계산 에러: {e}")
        return None


def calculate_ema(prices: pd.Series, period: int) -> Optional[float]:
    """
    지수 이동평균 (EMA) 계산
    
    Args:
        prices: 가격 시리즈
        period: 이동평균 기간
        
    Returns:
        EMA 값
    """
    if prices is None or len(prices) < period:
        return None
    
    try:
        return float(prices.ewm(span=period, adjust=False).mean().iloc[-1])
    except Exception as e:
        logger.error(f"EMA 계산 에러: {e}")
        return None


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Optional[Tuple[float, float, float]]:
    """
    MACD 계산
    
    Args:
        prices: 종가 시리즈
        fast_period: 빠른 EMA 기간 (기본 12)
        slow_period: 느린 EMA 기간 (기본 26)
        signal_period: 시그널 기간 (기본 9)
        
    Returns:
        (MACD, Signal, Histogram) 튜플
    """
    if prices is None or len(prices) < slow_period + signal_period:
        return None
    
    try:
        # EMAs
        fast_ema = prices.ewm(span=fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=slow_period, adjust=False).mean()
        
        # MACD Line
        macd_line = fast_ema - slow_ema
        
        # Signal Line
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return (
            float(macd_line.iloc[-1]),
            float(signal_line.iloc[-1]),
            float(histogram.iloc[-1])
        )
        
    except Exception as e:
        logger.error(f"MACD 계산 에러: {e}")
        return None


def detect_fvg(
    df: pd.DataFrame,
    min_gap_percent: float = 0.1,
    lookback: int = 50
) -> Optional[FVGResult]:
    """
    ICT Fair Value Gap (FVG) 탐지
    
    FVG는 3개의 캔들 사이에서 급격한 상승/하락으로 인해 
    매물대가 비어있는 구간(Gap)을 찾습니다.
    
    상승 FVG: candle[N-2].high < candle[N].low
    하락 FVG: candle[N-2].low > candle[N].high
    
    Args:
        df: OHLCV DataFrame (open, high, low, close, volume)
        min_gap_percent: 최소 갭 크기 (%, 기본 0.1%)
        lookback: 탐지할 캔들 수 (기본 50)
        
    Returns:
        FVGResult or None
    """
    if df is None or len(df) < 3:
        logger.warning("FVG 탐지 불가: 데이터 부족")
        return None
    
    try:
        # 최근 N개 캔들만 사용
        df = df.tail(lookback).reset_index(drop=False)
        
        # 가장 최근의 미충전 FVG를 찾기 (뒤에서부터 탐색)
        for i in range(len(df) - 1, 2, -1):
            candle_n2 = df.iloc[i-2]  # 2개 전 캔들
            candle_n1 = df.iloc[i-1]  # 모멘텀 캔들 (가장 긴 캔들)
            candle_n = df.iloc[i]     # 현재 캔들
            
            # 상승 FVG: N-2의 고가 < N의 저가 (갭 발생)
            if candle_n2['high'] < candle_n['low']:
                gap_bottom = candle_n2['high']
                gap_top = candle_n['low']
                gap_size = gap_top - gap_bottom
                gap_percent = (gap_size / gap_bottom) * 100
                
                # 최소 갭 크기 체크
                if gap_percent >= min_gap_percent:
                    # 갭이 아직 충전되지 않았는지 확인 (최근 캔들들이 갭을 채우지 않음)
                    filled = False
                    for j in range(i + 1, len(df)):
                        if df.iloc[j]['low'] <= gap_bottom:
                            filled = True
                            break
                    
                    if not filled:
                        # 시간 정보
                        time_str = None
                        if 'index' in df.columns:
                            time_str = str(candle_n1['index'])
                        
                        return FVGResult(
                            found=True,
                            direction="BULLISH",
                            gap_top=gap_top,
                            gap_bottom=gap_bottom,
                            stop_loss=candle_n1['low'],
                            take_profit=candle_n1['high'],
                            momentum_candle_time=time_str,
                            gap_size=gap_size,
                            gap_percent=gap_percent
                        )
            
            # 하락 FVG: N-2의 저가 > N의 고가 (갭 발생)
            if candle_n2['low'] > candle_n['high']:
                gap_top = candle_n2['low']
                gap_bottom = candle_n['high']
                gap_size = gap_top - gap_bottom
                gap_percent = (gap_size / gap_bottom) * 100
                
                # 최소 갭 크기 체크
                if gap_percent >= min_gap_percent:
                    # 갭이 아직 충전되지 않았는지 확인
                    filled = False
                    for j in range(i + 1, len(df)):
                        if df.iloc[j]['high'] >= gap_top:
                            filled = True
                            break
                    
                    if not filled:
                        time_str = None
                        if 'index' in df.columns:
                            time_str = str(candle_n1['index'])
                        
                        return FVGResult(
                            found=True,
                            direction="BEARISH",
                            gap_top=gap_top,
                            gap_bottom=gap_bottom,
                            stop_loss=candle_n1['high'],
                            take_profit=candle_n1['low'],
                            momentum_candle_time=time_str,
                            gap_size=gap_size,
                            gap_percent=gap_percent
                        )
        
        # FVG 없음
        return FVGResult(
            found=False,
            direction="NONE",
            gap_top=0,
            gap_bottom=0,
            stop_loss=0,
            take_profit=0,
            momentum_candle_time=None,
            gap_size=0,
            gap_percent=0
        )
        
    except Exception as e:
        logger.error(f"FVG 탐지 에러: {e}")
        return None


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== Technical Indicators Test ===\n")
    
    # 실제 데이터 가져오기 (30분봉)
    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute30", count=100)
    
    if df is not None:
        prices = df['close']
        
        # RSI
        rsi = calculate_rsi(prices)
        if rsi:
            print(f"📊 {rsi}")
        
        # Bollinger Bands
        bb = calculate_bollinger_bands(prices)
        if bb:
            print(f"📈 {bb}")
        
        # SMA/EMA
        sma20 = calculate_sma(prices, 20)
        ema20 = calculate_ema(prices, 20)
        if sma20 and ema20:
            print(f"📉 SMA(20): ₩{sma20:,.0f}, EMA(20): ₩{ema20:,.0f}")
        
        # MACD
        macd = calculate_macd(prices)
        if macd:
            print(f"📊 MACD: {macd[0]:,.0f}, Signal: {macd[1]:,.0f}, Hist: {macd[2]:,.0f}")
        
        # FVG (ICT)
        print("\n=== ICT FVG Test ===")
        fvg = detect_fvg(df, min_gap_percent=0.05)
        if fvg:
            print(f"🎯 {fvg}")
            if fvg.found:
                current_price = pyupbit.get_current_price("KRW-BTC")
                print(f"   현재가: ₩{current_price:,.0f}")
                if fvg.direction == "BULLISH":
                    if current_price <= fvg.gap_top and current_price >= fvg.gap_bottom:
                        print(f"   ✅ 매수 진입 가능 (갭 영역 내)")
                    elif current_price > fvg.gap_top:
                        print(f"   ⏳ 대기 중 (가격이 갭 위)")
                    else:
                        print(f"   ❌ 손절 영역 (갭 하단 이탈)")
    else:
        print("❌ 데이터 조회 실패")

