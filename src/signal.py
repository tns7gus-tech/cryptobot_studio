"""
CryptoBot Studio - Unified Trade Signal
모든 전략에서 사용하는 통합 신호 클래스
"""
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any


@dataclass
class TradeSignal:
    """
    통합 거래 신호
    
    모든 전략(ICT, Trend, Hybrid)에서 공통으로 사용하는 신호 클래스.
    기존 Signal, HybridSignal, TrendSignal을 통합.
    """
    # 필수 필드
    action: Literal["BUY", "SELL", "HOLD"]
    strategy: str  # 전략 이름 (예: "ICT", "TREND", "HYBRID")
    confidence: float  # 신뢰도 (0.0 ~ 1.0)
    reason: str  # 신호 발생 사유
    
    # 선택 필드 (전략별로 다름)
    take_profit: float = 0.0  # 익절 %
    stop_loss: float = 0.0  # 손절 %
    position_size_ratio: float = 0.0  # 포지션 크기 비율
    
    # 메타데이터 (RSI, EMA 등 전략별 추가 정보)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        emoji = "🟢" if self.action == "BUY" else "🔴" if self.action == "SELL" else "⏸️"
        conf_str = f"{self.confidence:.0%}"
        
        if self.position_size_ratio > 0:
            return f"{emoji} [{self.strategy}] {self.action}: {self.reason} (신뢰도: {conf_str}, 크기: {self.position_size_ratio:.1%})"
        else:
            return f"{emoji} [{self.strategy}] {self.action}: {self.reason} (신뢰도: {conf_str})"
    
    @classmethod
    def hold(cls, strategy: str = "NONE", reason: str = "대기") -> "TradeSignal":
        """HOLD 신호 빠른 생성"""
        return cls(
            action="HOLD",
            strategy=strategy,
            confidence=0.3,
            reason=reason
        )
    
    @classmethod
    def buy(
        cls,
        strategy: str,
        reason: str,
        confidence: float = 0.7,
        take_profit: float = 0.0,
        stop_loss: float = 0.0,
        position_size_ratio: float = 0.0,
        **metadata
    ) -> "TradeSignal":
        """BUY 신호 빠른 생성"""
        return cls(
            action="BUY",
            strategy=strategy,
            confidence=confidence,
            reason=reason,
            take_profit=take_profit,
            stop_loss=stop_loss,
            position_size_ratio=position_size_ratio,
            metadata=metadata
        )
    
    @classmethod
    def sell(
        cls,
        strategy: str,
        reason: str,
        confidence: float = 0.95,
        **metadata
    ) -> "TradeSignal":
        """SELL 신호 빠른 생성"""
        return cls(
            action="SELL",
            strategy=strategy,
            confidence=confidence,
            reason=reason,
            metadata=metadata
        )
    
    def get_meta(self, key: str, default: Any = None) -> Any:
        """메타데이터 조회"""
        return self.metadata.get(key, default)


# 하위 호환용 별칭 (점진적 마이그레이션)
Signal = TradeSignal
HybridSignal = TradeSignal
TrendSignal = TradeSignal
