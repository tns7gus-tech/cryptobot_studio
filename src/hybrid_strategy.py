"""
CryptoBot Studio - Hybrid Strategy (ICT + Trend Following)
고승률 ICT + 고빈도 추세추종 하이브리드 전략
목표: 매일 1% 수익률 달성
"""
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from strategies import Signal, ICTStrategy
from trend_analyzer import TrendFollowingAnalyzer, TrendSignal
from indicators import detect_order_block, detect_fvg, detect_liquidity_pool


@dataclass
class HybridSignal:
    """하이브리드 신호"""
    action: str  # "BUY", "SELL", "HOLD"
    strategy_type: str  # "ICT" or "TREND"
    confidence: float
    reason: str
    position_size_ratio: float  # 포지션 크기 비율
    take_profit: float  # 익절 %
    stop_loss: float  # 손절 %
    
    def __str__(self):
        emoji = "🟢" if self.action == "BUY" else "🔴" if self.action == "SELL" else "⏸️"
        return f"{emoji} [{self.strategy_type}] {self.action}: {self.reason} (신뢰도: {self.confidence:.0%}, 크기: {self.position_size_ratio:.1%})"


class HybridStrategy:
    """
    ICT + Trend Following 하이브리드 전략
    
    동작 방식:
    1. ICT 신호 우선 확인 (1시간봉, 고승률)
       - Confluence 80점 이상이면 큰 포지션으로 진입
    2. ICT 신호 없으면 추세추종 확인 (5분봉, 고빈도)
       - 작은 포지션으로 스캘핑
    3. 일일 목표 1% 달성 시 보수적 모드 전환
    
    설정:
    - ICT: 포트폴리오 5%, 익절 2%, 손절 1%
    - 추세: 포트폴리오 1%, 익절 0.3%, 손절 0.5%
    """
    
    def __init__(
        self,
        daily_target: float = 1.0,  # 일일 목표 %
        ict_position_ratio: float = 0.05,  # ICT 포지션 크기 (5%)
        trend_position_ratio: float = 0.01,  # 추세 포지션 크기 (1%)
        ict_take_profit: float = 2.0,  # ICT 익절 %
        ict_stop_loss: float = 1.0,  # ICT 손절 %
        trend_take_profit: float = 0.3,  # 추세 익절 %
        trend_stop_loss: float = 0.5,  # 추세 손절 %
    ):
        self.daily_target = daily_target
        self.ict_position_ratio = ict_position_ratio
        self.trend_position_ratio = trend_position_ratio
        self.ict_take_profit = ict_take_profit
        self.ict_stop_loss = ict_stop_loss
        self.trend_take_profit = trend_take_profit
        self.trend_stop_loss = trend_stop_loss
        
        # 전략 인스턴스
        self.ict_strategy = ICTStrategy(
            confluence_threshold=50,   # 최적화: 80 -> 50 완화
            min_rr_ratio=2.0,
            take_profit=ict_take_profit,
            stop_loss=ict_stop_loss
        )
        
        self.trend_analyzer = TrendFollowingAnalyzer(
            take_profit=trend_take_profit,
            stop_loss=trend_stop_loss
        )
        
        # 일일 통계
        self.daily_profit = 0.0
        self.trade_count = 0
        self.last_reset = datetime.now()
    
    @property
    def name(self) -> str:
        return "Hybrid_ICT_Trend"
    
    def reset_daily(self):
        """일일 리셋"""
        self.daily_profit = 0.0
        self.trade_count = 0
        self.last_reset = datetime.now()
        logger.info("📅 일일 통계 리셋")
    
    def update_profit(self, profit_percent: float):
        """수익률 업데이트"""
        self.daily_profit += profit_percent
        self.trade_count += 1
    
    def is_target_achieved(self) -> bool:
        """일일 목표 달성 여부"""
        return self.daily_profit >= self.daily_target
    
    def get_position_size_multiplier(self) -> float:
        """
        포지션 크기 배수 (목표 달성 후 축소)
        """
        if self.daily_profit >= self.daily_target:
            return 0.5  # 50% 축소
        elif self.daily_profit >= self.daily_target * 0.7:
            return 0.75  # 25% 축소
        else:
            return 1.0
    
    def analyze(
        self,
        df_1h: Optional["pd.DataFrame"] = None,  # 1시간봉 (ICT용)
        df_5m: Optional["pd.DataFrame"] = None,  # 5분봉 (추세용)
        current_price: float = None,
        in_position: bool = False,
        entry_price: float = None,
        position_strategy: str = None,  # 현재 포지션의 전략 타입
        **kwargs
    ) -> HybridSignal:
        """
        하이브리드 분석 수행
        
        Args:
            df_1h: 1시간봉 OHLCV (ICT 분석용)
            df_5m: 5분봉 OHLCV (추세 분석용)
            current_price: 현재가
            in_position: 포지션 보유 여부
            entry_price: 진입가
            position_strategy: 포지션의 원래 전략 ("ICT" or "TREND")
        """
        if current_price is None:
            return HybridSignal(
                action="HOLD",
                strategy_type="NONE",
                confidence=0.0,
                reason="현재가 정보 없음",
                position_size_ratio=0,
                take_profit=0,
                stop_loss=0
            )
        
        size_mult = self.get_position_size_multiplier()
        
        # 포지션 보유 중 - 해당 전략으로 청산 판단
        if in_position and entry_price and entry_price > 0:
            profit_rate = ((current_price - entry_price) / entry_price) * 100
            
            if position_strategy == "ICT":
                # ICT 익절/손절
                if profit_rate >= self.ict_take_profit:
                    return HybridSignal(
                        action="SELL",
                        strategy_type="ICT",
                        confidence=0.95,
                        reason=f"ICT 익절: +{profit_rate:.2f}%",
                        position_size_ratio=self.ict_position_ratio * size_mult,
                        take_profit=self.ict_take_profit,
                        stop_loss=self.ict_stop_loss
                    )
                if profit_rate <= -self.ict_stop_loss:
                    return HybridSignal(
                        action="SELL",
                        strategy_type="ICT",
                        confidence=0.95,
                        reason=f"ICT 손절: {profit_rate:.2f}%",
                        position_size_ratio=self.ict_position_ratio * size_mult,
                        take_profit=self.ict_take_profit,
                        stop_loss=self.ict_stop_loss
                    )
            else:
                # 추세 익절/손절
                if profit_rate >= self.trend_take_profit:
                    return HybridSignal(
                        action="SELL",
                        strategy_type="TREND",
                        confidence=0.95,
                        reason=f"추세 익절: +{profit_rate:.2f}%",
                        position_size_ratio=self.trend_position_ratio * size_mult,
                        take_profit=self.trend_take_profit,
                        stop_loss=self.trend_stop_loss
                    )
                if profit_rate <= -self.trend_stop_loss:
                    return HybridSignal(
                        action="SELL",
                        strategy_type="TREND",
                        confidence=0.95,
                        reason=f"추세 손절: {profit_rate:.2f}%",
                        position_size_ratio=self.trend_position_ratio * size_mult,
                        take_profit=self.trend_take_profit,
                        stop_loss=self.trend_stop_loss
                    )
            
            # 포지션 유지
            return HybridSignal(
                action="HOLD",
                strategy_type=position_strategy or "UNKNOWN",
                confidence=0.5,
                reason=f"포지션 유지: {profit_rate:+.2f}%",
                position_size_ratio=0,
                take_profit=0,
                stop_loss=0
            )
        
        # 포지션 없음 - 새 진입 신호 탐색
        
        # 1. ICT 신호 우선 확인 (1시간봉)
        if df_1h is not None and not self.is_target_achieved():
            ict_signal = self.ict_strategy.analyze(
                ohlcv_df=df_1h,
                current_price=current_price,
                in_position=False
            )
            
            if ict_signal.action == "BUY" and ict_signal.confidence >= 0.7:
                logger.info(f"🎯 ICT 신호 발견: {ict_signal.reason}")
                return HybridSignal(
                    action="BUY",
                    strategy_type="ICT",
                    confidence=ict_signal.confidence,
                    reason=f"ICT: {ict_signal.reason}",
                    position_size_ratio=self.ict_position_ratio * size_mult,
                    take_profit=self.ict_take_profit,
                    stop_loss=self.ict_stop_loss
                )
        
        # 2. 추세 신호 확인 (5분봉)
        if df_5m is not None:
            trend_signal = self.trend_analyzer.analyze(
                df=df_5m,
                current_price=current_price,
                in_position=False
            )
            
            if trend_signal.action == "BUY" and trend_signal.confidence >= 0.6:
                # 목표 달성 후에는 추세 신호도 축소
                if self.is_target_achieved():
                    size_mult *= 0.5
                
                return HybridSignal(
                    action="BUY",
                    strategy_type="TREND",
                    confidence=trend_signal.confidence,
                    reason=f"추세: {trend_signal.reason}",
                    position_size_ratio=self.trend_position_ratio * size_mult,
                    take_profit=self.trend_take_profit,
                    stop_loss=self.trend_stop_loss
                )
        
        # 신호 없음
        return HybridSignal(
            action="HOLD",
            strategy_type="NONE",
            confidence=0.3,
            reason="진입 신호 없음",
            position_size_ratio=0,
            take_profit=0,
            stop_loss=0
        )
    
    def get_daily_stats(self) -> dict:
        """일일 통계 반환"""
        return {
            "daily_profit": self.daily_profit,
            "trade_count": self.trade_count,
            "target_achieved": self.is_target_achieved(),
            "target": self.daily_target
        }


# Test
if __name__ == "__main__":
    import pyupbit
    
    print("=== Hybrid Strategy Test ===\n")
    
    symbol = "KRW-ETH"
    df_1h = pyupbit.get_ohlcv(symbol, interval="minute60", count=100)
    df_5m = pyupbit.get_ohlcv(symbol, interval="minute5", count=50)
    
    if df_1h is not None and df_5m is not None:
        current_price = pyupbit.get_current_price(symbol)
        print(f"📌 {symbol} 현재가: ₩{current_price:,.0f}\n")
        
        strategy = HybridStrategy()
        signal = strategy.analyze(
            df_1h=df_1h,
            df_5m=df_5m,
            current_price=current_price,
            in_position=False
        )
        
        print(f"📊 신호: {signal}")
        print(f"   전략: {signal.strategy_type}")
        print(f"   포지션 크기: {signal.position_size_ratio:.1%}")
        print(f"   익절: {signal.take_profit}% / 손절: {signal.stop_loss}%")
    else:
        print("❌ 데이터 조회 실패")
