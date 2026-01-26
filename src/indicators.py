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


@dataclass
class OrderBlockResult:
    """ICT Order Block 탐지 결과"""
    found: bool
    direction: str  # "BULLISH" or "BEARISH" or "NONE"
    level: float  # OB 핵심 레벨 가격
    zone_top: float  # OB 영역 상단
    zone_bottom: float  # OB 영역 하단
    strength: int  # 연속 캔들 수 (강도 지표)
    candle_time: Optional[str]  # OB 발생 캔들 시간
    
    def __str__(self):
        if not self.found:
            return "OrderBlock: 미발견"
        emoji = "🟢" if self.direction == "BULLISH" else "🔴"
        return f"{emoji} OB({self.direction}): ₩{self.zone_bottom:,.0f}~₩{self.zone_top:,.0f} (강도: {self.strength})"


@dataclass
class LiquidityPoolResult:
    """ICT Liquidity Pool 탐지 결과"""
    found: bool
    pool_type: str  # "SWING_HIGH" or "SWING_LOW" or "NONE"
    level: float  # 유동성 레벨 (스윙 포인트 가격)
    zone_top: float  # 유동성 영역 상단
    zone_bottom: float  # 유동성 영역 하단
    touch_count: int  # 해당 레벨 터치 횟수 (미체결 주문 축적 추정)
    
    def __str__(self):
        if not self.found:
            return "LiquidityPool: 미발견"
        emoji = "🔼" if self.pool_type == "SWING_HIGH" else "🔽"
        return f"{emoji} LP({self.pool_type}): ₩{self.level:,.0f} (터치: {self.touch_count}회)"


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


def detect_order_block(
    df: pd.DataFrame,
    lookback: int = 30,
    min_consecutive: int = 2,
    min_body_ratio: float = 0.5
) -> Optional[OrderBlockResult]:
    """
    ICT Order Block 탐지
    
    Order Block = 기관이 대량 매수/매도한 구간의 마지막 반대 캔들
    - Bullish OB: 강한 상승 전 마지막 하락 캔들 (지지 영역)
    - Bearish OB: 강한 하락 전 마지막 상승 캔들 (저항 영역)
    
    Args:
        df: OHLCV DataFrame
        lookback: 탐지할 캔들 수
        min_consecutive: 최소 연속 캔들 수 (강도)
        min_body_ratio: 최소 몸통 비율 (0~1)
        
    Returns:
        OrderBlockResult
    """
    if df is None or len(df) < lookback:
        return None
    
    try:
        df = df.tail(lookback).reset_index(drop=False)
        
        # 뒤에서부터 탐색 (최신 OB 찾기)
        for i in range(len(df) - 1, min_consecutive + 1, -1):
            # 최근 연속 상승/하락 체크
            consecutive_up = 0
            consecutive_down = 0
            
            for j in range(i, max(i - 5, 0), -1):
                candle = df.iloc[j]
                if candle['close'] > candle['open']:
                    consecutive_up += 1
                    consecutive_down = 0
                else:
                    consecutive_down += 1
                    consecutive_up = 0
                    
                if consecutive_up >= min_consecutive or consecutive_down >= min_consecutive:
                    break
            
            # Bullish OB: 연속 상승 직전의 마지막 음봉
            if consecutive_up >= min_consecutive:
                # OB 캔들 찾기 (상승 직전의 음봉)
                ob_idx = i - consecutive_up
                if ob_idx >= 0:
                    ob_candle = df.iloc[ob_idx]
                    if ob_candle['close'] < ob_candle['open']:  # 음봉 확인
                        body = abs(ob_candle['close'] - ob_candle['open'])
                        total_range = ob_candle['high'] - ob_candle['low']
                        body_ratio = body / total_range if total_range > 0 else 0
                        
                        if body_ratio >= min_body_ratio:
                            time_str = str(ob_candle['index']) if 'index' in df.columns else None
                            return OrderBlockResult(
                                found=True,
                                direction="BULLISH",
                                level=ob_candle['low'],
                                zone_top=ob_candle['open'],
                                zone_bottom=ob_candle['low'],
                                strength=consecutive_up,
                                candle_time=time_str
                            )
            
            # Bearish OB: 연속 하락 직전의 마지막 양봉
            if consecutive_down >= min_consecutive:
                ob_idx = i - consecutive_down
                if ob_idx >= 0:
                    ob_candle = df.iloc[ob_idx]
                    if ob_candle['close'] > ob_candle['open']:  # 양봉 확인
                        body = abs(ob_candle['close'] - ob_candle['open'])
                        total_range = ob_candle['high'] - ob_candle['low']
                        body_ratio = body / total_range if total_range > 0 else 0
                        
                        if body_ratio >= min_body_ratio:
                            time_str = str(ob_candle['index']) if 'index' in df.columns else None
                            return OrderBlockResult(
                                found=True,
                                direction="BEARISH",
                                level=ob_candle['high'],
                                zone_top=ob_candle['high'],
                                zone_bottom=ob_candle['close'],
                                strength=consecutive_down,
                                candle_time=time_str
                            )
        
        # OB 없음
        return OrderBlockResult(
            found=False,
            direction="NONE",
            level=0,
            zone_top=0,
            zone_bottom=0,
            strength=0,
            candle_time=None
        )
        
    except Exception as e:
        logger.error(f"Order Block 탐지 에러: {e}")
        return None


def detect_liquidity_pool(
    df: pd.DataFrame,
    lookback: int = 50,
    swing_period: int = 5,
    buffer_percent: float = 0.1
) -> Optional[LiquidityPoolResult]:
    """
    ICT Liquidity Pool 탐지
    
    Liquidity Pool = 손절매 주문이 몰려있을 것으로 예상되는 스윙 포인트
    - Swing High: 좌우 N개 캔들보다 높은 고점 (위에 손절매 주문 축적)
    - Swing Low: 좌우 N개 캔들보다 낮은 저점 (아래에 손절매 주문 축적)
    
    Args:
        df: OHLCV DataFrame
        lookback: 탐지할 캔들 수
        swing_period: 스윙 판단 기간 (좌우 각각)
        buffer_percent: 유동성 영역 버퍼 (%)
        
    Returns:
        LiquidityPoolResult
    """
    if df is None or len(df) < lookback:
        return None
    
    try:
        df = df.tail(lookback).reset_index(drop=True)
        
        swing_highs = []
        swing_lows = []
        
        # 스윙 포인트 탐지
        for i in range(swing_period, len(df) - swing_period):
            candle = df.iloc[i]
            
            # Swing High 체크
            is_swing_high = True
            for j in range(i - swing_period, i + swing_period + 1):
                if j != i and df.iloc[j]['high'] >= candle['high']:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append((i, candle['high']))
            
            # Swing Low 체크
            is_swing_low = True
            for j in range(i - swing_period, i + swing_period + 1):
                if j != i and df.iloc[j]['low'] <= candle['low']:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append((i, candle['low']))
        
        # 가장 최근의 스윙 포인트 선택
        current_price = df.iloc[-1]['close']
        
        # 현재가 기준으로 가장 가까운 LP 찾기
        closest_high = None
        closest_low = None
        
        if swing_highs:
            # 현재가 위의 가장 가까운 Swing High
            highs_above = [(idx, level) for idx, level in swing_highs if level > current_price]
            if highs_above:
                closest_high = min(highs_above, key=lambda x: x[1] - current_price)
        
        if swing_lows:
            # 현재가 아래의 가장 가까운 Swing Low
            lows_below = [(idx, level) for idx, level in swing_lows if level < current_price]
            if lows_below:
                closest_low = max(lows_below, key=lambda x: x[1])
        
        # 더 가까운 LP 반환
        if closest_high and closest_low:
            dist_high = closest_high[1] - current_price
            dist_low = current_price - closest_low[1]
            
            if dist_high < dist_low:
                level = closest_high[1]
                buffer = level * buffer_percent / 100
                return LiquidityPoolResult(
                    found=True,
                    pool_type="SWING_HIGH",
                    level=level,
                    zone_top=level + buffer,
                    zone_bottom=level - buffer,
                    touch_count=1
                )
            else:
                level = closest_low[1]
                buffer = level * buffer_percent / 100
                return LiquidityPoolResult(
                    found=True,
                    pool_type="SWING_LOW",
                    level=level,
                    zone_top=level + buffer,
                    zone_bottom=level - buffer,
                    touch_count=1
                )
        elif closest_high:
            level = closest_high[1]
            buffer = level * buffer_percent / 100
            return LiquidityPoolResult(
                found=True,
                pool_type="SWING_HIGH",
                level=level,
                zone_top=level + buffer,
                zone_bottom=level - buffer,
                touch_count=1
            )
        elif closest_low:
            level = closest_low[1]
            buffer = level * buffer_percent / 100
            return LiquidityPoolResult(
                found=True,
                pool_type="SWING_LOW",
                level=level,
                zone_top=level + buffer,
                zone_bottom=level - buffer,
                touch_count=1
            )
        
        # LP 없음
        return LiquidityPoolResult(
            found=False,
            pool_type="NONE",
            level=0,
            zone_top=0,
            zone_bottom=0,
            touch_count=0
        )
        
    except Exception as e:
        logger.error(f"Liquidity Pool 탐지 에러: {e}")
        return None


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== ICT Technical Indicators Test ===\n")
    
    # ETH 데이터로 테스트 (BTC 제외 - 사용자 요청)
    symbol = "KRW-ETH"
    df = pyupbit.get_ohlcv(symbol, interval="minute60", count=100)
    
    if df is not None:
        prices = df['close']
        current_price = pyupbit.get_current_price(symbol)
        print(f"📌 {symbol} 현재가: ₩{current_price:,.0f}\n")
        
        # 1. Order Block
        print("=== Order Block ===")
        ob = detect_order_block(df)
        if ob:
            print(f"   {ob}")
            if ob.found:
                print(f"   영역: ₩{ob.zone_bottom:,.0f} ~ ₩{ob.zone_top:,.0f}")
        
        # 2. Fair Value Gap
        print("\n=== Fair Value Gap ===")
        fvg = detect_fvg(df, min_gap_percent=0.03)
        if fvg:
            print(f"   {fvg}")
        
        # 3. Liquidity Pool
        print("\n=== Liquidity Pool ===")
        lp = detect_liquidity_pool(df)
        if lp:
            print(f"   {lp}")
            if lp.found:
                print(f"   영역: ₩{lp.zone_bottom:,.0f} ~ ₩{lp.zone_top:,.0f}")
        
        # 4. Confluence 체크
        print("\n=== ICT Confluence 분석 ===")
        score = 0
        if ob and ob.found: 
            score += 30
            print(f"   ✅ Order Block 발견 (+30점)")
        if fvg and fvg.found: 
            score += 30
            print(f"   ✅ FVG 발견 (+30점)")
        if lp and lp.found: 
            score += 20
            print(f"   ✅ Liquidity Pool 발견 (+20점)")
        
        print(f"\n   📊 총점: {score}점 / 80점 {'✅ 진입 가능' if score >= 80 else '❌ 대기'}")
        
    else:
        print("❌ 데이터 조회 실패")


