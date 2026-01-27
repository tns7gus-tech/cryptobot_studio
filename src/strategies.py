"""
CryptoBot Studio - Trading Strategies
ICT-based trading strategies (cleaned version)

Removed deprecated strategies:
- OrderbookScalpingStrategy
- MACDVolumeStrategy
- RSIEMAStrategy
- BollingerBandStrategy
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


class ICTStrategy(BaseStrategy):
    """
    ICT Confluence 전략 (스캘핑 대체)
    
    3가지 ICT 요소 중 2개 이상 겹칠 때 진입:
    - Order Block (OB): 30점
    - Fair Value Gap (FVG): 30점  
    - Liquidity Pool (LP): 20점
    - Multi-Timeframe 일치: 20점
    
    총점 80점 이상 + RR 1:2 이상 시 진입
    
    설정:
    - 체크 간격: 12분
    - 대상: ETH, USDT, SOL (BTC 제외)
    - 목표: 일일 1% 안정 수익
    """
    
    def __init__(
        self,
        confluence_threshold: int = 80,  # 진입 최소 점수
        min_rr_ratio: float = 2.0,        # 최소 손익비
        take_profit: float = 2.0,         # 익절 %
        stop_loss: float = 1.0            # 손절 %
    ):
        self.confluence_threshold = confluence_threshold
        self.min_rr_ratio = min_rr_ratio
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self._last_signal = None
        
    @property
    def name(self) -> str:
        return "ICT_Confluence"
    
    def calculate_confluence_score(
        self,
        ob_result,
        fvg_result,
        lp_result,
        current_price: float = None
    ) -> tuple:
        """
        Confluence 점수 계산
        
        Returns:
            (총점, 상세내역 dict)
        """
        score = 0
        details = {
            "order_block": 0,
            "fvg": 0,
            "liquidity_pool": 0,
            "price_in_zone": 0
        }
        
        # 1. Order Block (+30점)
        if ob_result and ob_result.found:
            details["order_block"] = 30
            score += 30
            
            # 가격이 OB 영역 내에 있으면 추가 점수
            if current_price:
                if ob_result.zone_bottom <= current_price <= ob_result.zone_top:
                    details["price_in_zone"] += 10
                    score += 10
        
        # 2. Fair Value Gap (+30점)
        if fvg_result and fvg_result.found:
            details["fvg"] = 30
            score += 30
            
            # 가격이 FVG 영역 내에 있으면 추가 점수
            if current_price:
                if fvg_result.gap_bottom <= current_price <= fvg_result.gap_top:
                    details["price_in_zone"] += 10
                    score += 10
        
        # 3. Liquidity Pool (+20점)
        if lp_result and lp_result.found:
            details["liquidity_pool"] = 20
            score += 20
        
        return score, details
    
    def analyze(
        self,
        ohlcv_df=None,
        current_price: float = None,
        entry_price: float = None,
        in_position: bool = False,
        ob_result=None,
        fvg_result=None,
        lp_result=None,
        **kwargs
    ) -> Signal:
        """
        ICT Confluence 분석
        
        Args:
            ohlcv_df: OHLCV DataFrame (주 타임프레임)
            current_price: 현재가
            entry_price: 진입가 (포지션 보유 시)
            in_position: 포지션 보유 여부
            ob_result: OrderBlockResult (사전 계산된 경우)
            fvg_result: FVGResult (사전 계산된 경우)
            lp_result: LiquidityPoolResult (사전 계산된 경우)
            
        Returns:
            Signal
        """
        from indicators import (
            detect_order_block, detect_fvg, detect_liquidity_pool,
            OrderBlockResult, FVGResult, LiquidityPoolResult
        )
        
        # 현재가 체크
        if current_price is None:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="현재가 정보 없음"
            )
        
        # 포지션 보유 중인 경우 - 익절/손절 판단
        if in_position and entry_price and entry_price > 0:
            profit_rate = ((current_price - entry_price) / entry_price) * 100
            
            # 익절 (2% 이상)
            if profit_rate >= self.take_profit:
                return Signal(
                    action="SELL",
                    strategy=self.name,
                    confidence=0.95,
                    reason=f"익절: +{profit_rate:.2f}% (목표: {self.take_profit}%)"
                )
            
            # 손절 (-1% 이하)
            if profit_rate <= -self.stop_loss:
                return Signal(
                    action="SELL",
                    strategy=self.name,
                    confidence=0.95,
                    reason=f"손절: {profit_rate:.2f}% (한도: -{self.stop_loss}%)"
                )
            
            # 포지션 유지
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.6,
                reason=f"포지션 유지: {profit_rate:+.2f}% (익절: +{self.take_profit}%, 손절: -{self.stop_loss}%)"
            )
        
        # 포지션 없는 경우 - ICT 분석
        if ohlcv_df is None:
            return Signal(
                action="HOLD",
                strategy=self.name,
                confidence=0.0,
                reason="OHLCV 데이터 없음"
            )
        
        # ICT 지표 계산 (사전 계산되지 않은 경우)
        if ob_result is None:
            ob_result = detect_order_block(ohlcv_df)
        if fvg_result is None:
            fvg_result = detect_fvg(ohlcv_df, min_gap_percent=0.05)
        if lp_result is None:
            lp_result = detect_liquidity_pool(ohlcv_df)
        
        # Confluence 점수 계산
        score, details = self.calculate_confluence_score(
            ob_result, fvg_result, lp_result, current_price
        )
        
        logger.debug(f"ICT Score: {score} (OB:{details['order_block']}, FVG:{details['fvg']}, LP:{details['liquidity_pool']}, Zone:{details['price_in_zone']})")
        
        # Bullish 신호 체크
        if score >= self.confluence_threshold:
            # 방향 결정 (OB 또는 FVG 방향 기준)
            direction = "BULLISH"
            if ob_result and ob_result.found:
                direction = ob_result.direction
            elif fvg_result and fvg_result.found:
                direction = fvg_result.direction
            
            if direction == "BULLISH":
                # 손익비 계산
                stop_loss_price = current_price * (1 - self.stop_loss / 100)
                take_profit_price = current_price * (1 + self.take_profit / 100)
                risk = current_price - stop_loss_price
                reward = take_profit_price - current_price
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio >= self.min_rr_ratio:
                    confidence = min(0.95, 0.7 + (score - 80) * 0.01)
                    return Signal(
                        action="BUY",
                        strategy=self.name,
                        confidence=confidence,
                        reason=f"ICT Confluence {score}점 (OB:{details['order_block']}, FVG:{details['fvg']}, LP:{details['liquidity_pool']}) RR:{rr_ratio:.1f}"
                    )
                else:
                    return Signal(
                        action="HOLD",
                        strategy=self.name,
                        confidence=0.5,
                        reason=f"점수 충족({score}점) but 손익비 부족 (RR:{rr_ratio:.1f} < {self.min_rr_ratio})"
                    )
            
            elif direction == "BEARISH":
                # 하락 신호는 매도용 (현재는 BUY 봇이므로 HOLD)
                return Signal(
                    action="HOLD",
                    strategy=self.name,
                    confidence=0.4,
                    reason=f"ICT Bearish 신호 ({score}점) - 매수 대기"
                )
        
        # 점수 미달
        return Signal(
            action="HOLD",
            strategy=self.name,
            confidence=0.3,
            reason=f"Confluence {score}점 < {self.confluence_threshold}점 (OB:{details['order_block']}, FVG:{details['fvg']}, LP:{details['liquidity_pool']})"
        )


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== ICT Strategy Test ===\n")
    
    # ETH 테스트 (BTC 제외)
    symbol = "KRW-ETH"
    df = pyupbit.get_ohlcv(symbol, interval="minute60", count=100)
    
    if df is not None:
        current_price = pyupbit.get_current_price(symbol)
        print(f"📌 {symbol} 현재가: ₩{current_price:,.0f}\n")
        
        # ICT 전략 테스트
        strategy = ICTStrategy(
            confluence_threshold=80,
            min_rr_ratio=2.0,
            take_profit=2.0,
            stop_loss=1.0
        )
        
        signal = strategy.analyze(
            ohlcv_df=df,
            current_price=current_price,
            in_position=False
        )
        
        print(f"📊 신호: {signal}")
    else:
        print("❌ 데이터 조회 실패")
