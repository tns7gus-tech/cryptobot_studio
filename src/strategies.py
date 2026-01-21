"""
CryptoBot Studio - Trading Strategies
RSI and Bollinger Bands based trading strategies
"""
from abc import ABC, abstractmethod
from typing import Optional, Literal
from dataclasses import dataclass
from loguru import logger

from indicators import BollingerBandsResult


@dataclass
class Signal:
    """거래 신호"""
    action: Literal["BUY", "SELL", "HOLD"]
    strategy: str
    confidence: float  # 0.0 ~ 1.0
    reason: str
    
    def __str__(self):
        emoji = "🟢" if self.action == "BUY" else "🔴" if self.action == "SELL" else "⚪"
        return f"{emoji} {self.action} ({self.strategy}) - {self.reason} [신뢰도: {self.confidence:.0%}]"


class BaseStrategy(ABC):
    """전략 베이스 클래스"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def analyze(self, **kwargs) -> Signal:
        pass
class MACDVolumeStrategy(BaseStrategy):
    """
    MACD 크로스 + 거래량 급증 전략
    
    업비트 강세/약세지표의 "MACD크로스" 기반:
    - MACD 골든크로스(파랑) + 거래량 3배 이상 = 매수
    - MACD 데드크로스(빨강) + 거래량 3배 이상 = 매도
    
    거래량 조건이 충족되어야만 매매 실행 (노이즈 필터링)
    """
    
    def __init__(
        self,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        volume_multiplier: float = 3.0  # 이전 봉 대비 거래량 배수
    ):
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.volume_multiplier = volume_multiplier
    
    @property
    def name(self) -> str:
        return "MACD_Volume"
    
    def analyze(
        self,
        ohlcv_df=None,
        current_price: float = None,
        **kwargs
    ) -> Signal:
        """
        MACD 크로스 + 거래량 급증 분석
        """
        if ohlcv_df is None or len(ohlcv_df) < 35:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="데이터 부족"
            )
        
        prices = ohlcv_df['close']
        volumes = ohlcv_df['volume']
        current_price = current_price or float(prices.iloc[-1])
        
        # MACD 계산
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        
        # 현재 및 이전 MACD 값
        macd_now = float(macd_line.iloc[-1])
        macd_prev = float(macd_line.iloc[-2])
        signal_now = float(signal_line.iloc[-1])
        signal_prev = float(signal_line.iloc[-2])
        
        # MACD 크로스 판단
        # 골든크로스: MACD가 시그널을 상향 돌파 (파랑)
        golden_cross = macd_prev <= signal_prev and macd_now > signal_now
        # 데드크로스: MACD가 시그널을 하향 돌파 (빨강)
        death_cross = macd_prev >= signal_prev and macd_now < signal_now
        
        # 현재 MACD 상태 (파랑/빨강)
        is_bullish = macd_now > signal_now  # 파랑 (MACD > Signal)
        is_bearish = macd_now < signal_now  # 빨강 (MACD < Signal)
        
        # 거래량 급증 판단 (이전 봉 대비 3배 이상)
        current_volume = float(volumes.iloc[-1])
        prev_volume = float(volumes.iloc[-2])
        volume_ratio = current_volume / prev_volume if prev_volume > 0 else 0
        volume_spike = volume_ratio >= self.volume_multiplier
        
        # 평균 거래량 대비도 체크 (더 신뢰성 높은 판단)
        avg_volume = float(volumes.iloc[-20:].mean())
        volume_vs_avg = current_volume / avg_volume if avg_volume > 0 else 0
        
        logger.debug(f"MACD: {macd_now:.0f}, Signal: {signal_now:.0f}, Volume ratio: {volume_ratio:.1f}x")
        
        # 매수 신호: 골든크로스 또는 파랑 상태 + 거래량 3배 이상
        if (golden_cross or is_bullish) and volume_spike:
            confidence = min(0.95, 0.7 + (volume_ratio - 3) * 0.05)
            cross_type = "골든크로스" if golden_cross else "파랑(강세)"
            return Signal(
                action="BUY",
                strategy=self.name,
                confidence=confidence,
                reason=f"MACD {cross_type} + 거래량 {volume_ratio:.1f}배 급증"
            )
        
        # 매도 신호: 데드크로스 또는 빨강 상태 + 거래량 3배 이상
        if (death_cross or is_bearish) and volume_spike:
            confidence = min(0.95, 0.7 + (volume_ratio - 3) * 0.05)
            cross_type = "데드크로스" if death_cross else "빨강(약세)"
            return Signal(
                action="SELL",
                strategy=self.name,
                confidence=confidence,
                reason=f"MACD {cross_type} + 거래량 {volume_ratio:.1f}배 급증"
            )
        
        # HOLD 상태 설명
        macd_status = "파랑(강세)" if is_bullish else "빨강(약세)"
        if volume_spike:
            reason = f"MACD {macd_status}, 거래량 {volume_ratio:.1f}배 (크로스 대기)"
        else:
            reason = f"MACD {macd_status}, 거래량 {volume_ratio:.1f}배 (3배 미만)"
        
        return Signal(
            action="HOLD",
            strategy=self.name,
            confidence=0.5,
            reason=reason
        )


class RSIEMAStrategy(BaseStrategy):
    """
    RSI + EMA 크로스오버 전략 (5분봉 스캘핑)
    
    전문가들이 가장 보편적으로 사용하는 조합:
    - RSI 과매도(30 이하) + EMA 골든크로스 = 매수
    - RSI 과매수(70 이상) + EMA 데드크로스 = 매도
    
    추가 조건:
    - 가격이 EMA20 위에 있어야 매수 (상승 추세 확인)
    - 가격이 EMA20 아래에 있어야 매도 (하락 추세 확인)
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: int = 35,  # 5분봉은 덜 극단적으로
        rsi_overbought: int = 65,
        ema_fast: int = 9,
        ema_slow: int = 21
    ):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
    
    @property
    def name(self) -> str:
        return "RSI_EMA"
    
    def analyze(
        self,
        ohlcv_df=None,
        current_price: float = None,
        **kwargs
    ) -> Signal:
        """
        RSI + EMA 크로스오버 분석
        """
        from indicators import calculate_rsi, calculate_ema
        
        if ohlcv_df is None or len(ohlcv_df) < 30:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="데이터 부족"
            )
        
        prices = ohlcv_df['close']
        current_price = current_price or float(prices.iloc[-1])
        
        # RSI 계산
        rsi = calculate_rsi(prices, period=self.rsi_period, 
                           buy_threshold=self.rsi_oversold,
                           sell_threshold=self.rsi_overbought)
        
        if rsi is None:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="RSI 계산 실패"
            )
        
        # EMA 계산 (현재 및 이전 값)
        ema_fast_series = prices.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow_series = prices.ewm(span=self.ema_slow, adjust=False).mean()
        
        ema_fast_now = float(ema_fast_series.iloc[-1])
        ema_fast_prev = float(ema_fast_series.iloc[-2])
        ema_slow_now = float(ema_slow_series.iloc[-1])
        ema_slow_prev = float(ema_slow_series.iloc[-2])
        
        # 골든크로스: EMA9가 EMA21을 상향 돌파
        golden_cross = ema_fast_prev <= ema_slow_prev and ema_fast_now > ema_slow_now
        # 데드크로스: EMA9가 EMA21을 하향 돌파
        death_cross = ema_fast_prev >= ema_slow_prev and ema_fast_now < ema_slow_now
        
        # 추세 확인
        is_uptrend = current_price > ema_slow_now
        is_downtrend = current_price < ema_slow_now
        
        # 매수 신호: RSI 과매도 영역 + 상승 추세
        if rsi.value < self.rsi_oversold and is_uptrend:
            confidence = min(0.9, 0.6 + (self.rsi_oversold - rsi.value) * 0.02)
            return Signal(
                action="BUY",
                strategy=self.name,
                confidence=confidence,
                reason=f"RSI {rsi.value:.1f} 과매도 + 상승추세"
            )
        
        # 강한 매수 신호: 골든크로스 + RSI 중립 이하
        if golden_cross and rsi.value < 50:
            return Signal(
                action="BUY",
                strategy=self.name,
                confidence=0.85,
                reason=f"EMA 골든크로스 + RSI {rsi.value:.1f}"
            )
        
        # 매도 신호: RSI 과매수 영역 + 하락 추세
        if rsi.value > self.rsi_overbought and is_downtrend:
            confidence = min(0.9, 0.6 + (rsi.value - self.rsi_overbought) * 0.02)
            return Signal(
                action="SELL",
                strategy=self.name,
                confidence=confidence,
                reason=f"RSI {rsi.value:.1f} 과매수 + 하락추세"
            )
        
        # 강한 매도 신호: 데드크로스 + RSI 중립 이상
        if death_cross and rsi.value > 50:
            return Signal(
                action="SELL",
                strategy=self.name,
                confidence=0.85,
                reason=f"EMA 데드크로스 + RSI {rsi.value:.1f}"
            )
        
        # 기본: HOLD
        trend_str = "상승" if is_uptrend else "하락" if is_downtrend else "횡보"
        return Signal(
            action="HOLD",
            strategy=self.name,
            confidence=0.5,
            reason=f"RSI {rsi.value:.1f}, {trend_str}추세"
        )


class BollingerBandStrategy(BaseStrategy):
    """
    볼린저밴드 기반 매매 전략
    
    - 가격 < 하단밴드: 매수 신호
    - 가격 > 상단밴드: 매도 신호
    """
    
    @property
    def name(self) -> str:
        return "BollingerBand"
    
    def analyze(self, bb: BollingerBandsResult = None, **kwargs) -> Signal:
        """
        볼린저밴드 분석
        
        Args:
            bb: BollingerBandsResult 객체
            
        Returns:
            Signal
        """
        if bb is None:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="볼린저밴드 데이터 없음"
            )
        
        # 하단 밴드 돌파 (매수 신호)
        if bb.is_below_lower:
            # 신뢰도: 많이 이탈할수록 강한 신호
            confidence = min(1.0, max(0.5, 1.0 - bb.percent_b))
            return Signal(
                action="BUY",
                strategy=self.name,
                confidence=confidence,
                reason=f"가격 ₩{bb.current_price:,.0f} < 하단밴드 ₩{bb.lower:,.0f}"
            )
        
        # 상단 밴드 돌파 (매도 신호)
        if bb.is_above_upper:
            # 신뢰도: 많이 이탈할수록 강한 신호
            confidence = min(1.0, max(0.5, bb.percent_b))
            return Signal(
                action="SELL",
                strategy=self.name,
                confidence=confidence,
                reason=f"가격 ₩{bb.current_price:,.0f} > 상단밴드 ₩{bb.upper:,.0f}"
            )
        
        # 밴드 내
        return Signal(
            action="HOLD",
            strategy=self.name,
            confidence=0.5,
            reason=f"밴드 내 위치: {bb.percent_b:.1%}"
        )





class FVGStrategy(BaseStrategy):
    """
    ICT Fair Value Gap 전략
    
    3개의 캔들 사이에서 급격한 상승/하락으로 인해 매물대가 비어있는 구간(Gap)을 찾고,
    가격이 다시 그 구간으로 돌아올 때(Retracement) 진입합니다.
    
    상승 FVG:
    - 탐지: candle[N-2].high < candle[N].low
    - 매수: 가격이 갭 영역 내로 되돌아올 때
    - 손절: candle[N-1].low 이탈
    """
    
    def __init__(self, min_gap_percent: float = 0.05):
        """
        Args:
            min_gap_percent: 최소 갭 크기 (%, 기본 0.05%)
        """
        self.min_gap_percent = min_gap_percent
        self._active_fvg = None  # 현재 추적 중인 FVG
    
    @property
    def name(self) -> str:
        return "ICT_FVG"
    
    def analyze(
        self,
        ohlcv_df=None,
        current_price: float = None,
        fvg_result=None,
        **kwargs
    ) -> Signal:
        """
        FVG 전략 분석
        
        Args:
            ohlcv_df: OHLCV DataFrame
            current_price: 현재가
            fvg_result: 미리 계산된 FVGResult (선택사항)
            
        Returns:
            Signal
        """
        from indicators import detect_fvg, FVGResult
        
        # FVG 결과가 없으면 직접 탐지
        if fvg_result is None:
            if ohlcv_df is None:
                return Signal(
                    action="HOLD",
                    strategy=self.name,
                    confidence=0.0,
                    reason="OHLCV 데이터 없음"
                )
            fvg_result = detect_fvg(ohlcv_df, min_gap_percent=self.min_gap_percent)
        
        if fvg_result is None or not fvg_result.found:
            self._active_fvg = None
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.3,
                reason="FVG 미발견"
            )
        
        if current_price is None:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="현재가 정보 없음"
            )
        
        # FVG 발견됨 - 추적 시작
        self._active_fvg = fvg_result
        
        # 상승 FVG (Bullish)
        if fvg_result.direction == "BULLISH":
            # 손절 체크 (갭 하단 이탈 or 모멘텀 캔들 저가 이탈)
            if current_price < fvg_result.stop_loss:
                return Signal(
                    action="SELL",  # 손절
                    strategy=self.name,
                    confidence=0.9,
                    reason=f"손절: 현재가 ₩{current_price:,.0f} < SL ₩{fvg_result.stop_loss:,.0f}"
                )
            
            # 매수 진입 조건: 가격이 갭 영역 내로 진입
            if current_price <= fvg_result.gap_top and current_price >= fvg_result.gap_bottom:
                # 손익비 계산
                risk = current_price - fvg_result.stop_loss
                reward = fvg_result.take_profit - current_price
                rr_ratio = reward / risk if risk > 0 else 0
                
                confidence = min(0.9, 0.6 + (rr_ratio * 0.1))  # RR이 좋을수록 신뢰도 증가
                
                return Signal(
                    action="BUY",
                    strategy=self.name,
                    confidence=confidence,
                    reason=f"FVG 진입: 갭 ₩{fvg_result.gap_bottom:,.0f}~₩{fvg_result.gap_top:,.0f} 내 (RR:{rr_ratio:.1f})"
                )
            
            # 갭 위에서 대기 중
            if current_price > fvg_result.gap_top:
                return Signal(
                    action="HOLD",
                    strategy=self.name,
                    confidence=0.5,
                    reason=f"대기: 갭 ₩{fvg_result.gap_bottom:,.0f}~₩{fvg_result.gap_top:,.0f} 터치 대기 중"
                )
        
        # 하락 FVG (Bearish) - 현재는 매수만 지원
        if fvg_result.direction == "BEARISH":
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.4,
                reason=f"하락 FVG 감지 (매도 대기)"
            )
        
        return Signal(
            action="HOLD",
            strategy=self.name,
            confidence=0.3,
            reason="조건 미충족"
        )
    
    def get_active_fvg(self):
        """현재 활성 FVG 반환"""
        return self._active_fvg


# Test
if __name__ == "__main__":
    print("=== Strategy Test ===\n")
    
    # Mock data
    # BB 하단 돌파 테스트
    bb_below = BollingerBandsResult(
        upper=100000000,
        middle=95000000,
        lower=90000000,
        current_price=89000000,
        is_above_upper=False,
        is_below_lower=True,
        percent_b=-0.1
    )
    bb_strategy = BollingerBandStrategy()
    signal = bb_strategy.analyze(bb=bb_below)
    print(f"BB 하단 돌파: {signal}")
