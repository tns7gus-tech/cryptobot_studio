"""
CryptoBot Studio - Risk Management System
Controls trading frequency, amount, and daily loss limits (KRW based)
"""
import json
from datetime import datetime, date
from typing import Dict, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from loguru import logger

from config import settings


@dataclass
class DailyStats:
    """일일 통계"""
    date: str
    total_trades: int
    total_wagered: float  # KRW
    total_profit: float   # KRW
    win_count: int
    loss_count: int
    rsi_trades: int = 0
    bb_trades: int = 0
    combined_trades: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class RiskManager:
    """
    리스크 관리 시스템 (KRW 기준)
    
    - 일일 거래 횟수 제한
    - 1회 거래 금액 제한
    - 일일 손실 한도
    """
    
    def __init__(
        self,
        stats_file: str = "data/daily_stats.json",
        max_trade_amount: float = None,
        max_daily_trades: int = None,
        max_daily_loss: float = None
    ):
        self.stats_file = Path(stats_file)
        self.stats_file.parent.mkdir(exist_ok=True)
        
        # 설정에서 가져오거나 기본값 사용
        self.MAX_TRADE_AMOUNT = max_trade_amount or settings.trade_amount
        self.MAX_DAILY_TRADES = max_daily_trades or settings.max_daily_trades
        self.MAX_DAILY_LOSS = max_daily_loss or settings.max_daily_loss
        
        self.current_stats = self._load_today_stats()
        
        logger.info("📊 Risk Manager 초기화 완료")
        logger.info(f"   - 1회 최대 금액: ₩{self.MAX_TRADE_AMOUNT:,.0f}")
        logger.info(f"   - 일일 최대 거래: {self.MAX_DAILY_TRADES}회")
        logger.info(f"   - 일일 손실 한도: ₩{self.MAX_DAILY_LOSS:,.0f}")
    
    def _load_today_stats(self) -> DailyStats:
        """Load or create today's stats"""
        today = date.today().isoformat()
        
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if it's today's data
                if data.get('date') == today:
                    return DailyStats(**data)
            except Exception as e:
                logger.error(f"통계 로드 에러: {e}")
        
        # Create new stats for today
        return DailyStats(
            date=today,
            total_trades=0,
            total_wagered=0.0,
            total_profit=0.0,
            win_count=0,
            loss_count=0
        )
    
    def _save_stats(self):
        """Save current stats to file"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_stats.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"통계 저장 에러: {e}")
    
    def can_trade(self, amount: float = None) -> Tuple[bool, str]:
        """
        거래 가능 여부 확인
        
        Args:
            amount: 거래 금액 (선택)
            
        Returns:
            (거래 가능 여부, 사유)
        """
        # 날짜 변경 체크 (자동 리셋)
        today = date.today().isoformat()
        if self.current_stats.date != today:
            logger.info("📅 새로운 날 - 통계 리셋")
            self.current_stats = DailyStats(
                date=today,
                total_trades=0,
                total_wagered=0.0,
                total_profit=0.0,
                win_count=0,
                loss_count=0
            )
            self._save_stats()
        
        # 일일 거래 횟수 체크
        if self.current_stats.total_trades >= self.MAX_DAILY_TRADES:
            return False, f"일일 거래 횟수 초과 ({self.MAX_DAILY_TRADES}회)"
        
        # 일일 손실 체크
        if self.current_stats.total_profit < -self.MAX_DAILY_LOSS:
            return False, f"일일 손실 한도 초과 (₩{abs(self.current_stats.total_profit):,.0f})"
        
        # 거래 금액 체크
        if amount:
            if amount > self.MAX_TRADE_AMOUNT:
                return False, f"거래 금액 ₩{amount:,.0f} > 한도 ₩{self.MAX_TRADE_AMOUNT:,.0f}"
            
            # 손실 가능성 체크 (손절가 기준)
            # 5,000원 진입 시 100% 손실이 아니라, 설정된 손절률(예: 1%) + 슬리피지 여유분까지만 리스크로 산정
            estimated_loss = amount * (settings.scalping_stop_loss / 100) * 1.2
            
            # 현재 누적 손익 - 이번 거래 예상 손실 < -일일 손실 한도
            potential_total_profit = self.current_stats.total_profit - estimated_loss
            
            if potential_total_profit < -self.MAX_DAILY_LOSS:
                return False, f"잠재 손실 포함 한도 초과 (여유: ₩{(self.MAX_DAILY_LOSS + self.current_stats.total_profit):,.0f})"
        
        return True, "OK"
    
    def record_trade(
        self,
        amount: float,
        profit: float,
        strategy: str = "unknown",
        won: bool = None
    ):
        """
        거래 기록
        
        Args:
            amount: 거래 금액 (KRW)
            profit: 손익 (양수=수익, 음수=손실)
            strategy: 사용된 전략
            won: 승/패 여부 (None이면 profit으로 추론)
        """
        self.current_stats.total_trades += 1
        self.current_stats.total_wagered += amount
        self.current_stats.total_profit += profit
        
        if won is None:
            won = profit > 0
        
        if won:
            self.current_stats.win_count += 1
        else:
            self.current_stats.loss_count += 1
        
        # 전략별 카운트
        strategy_lower = strategy.lower()
        if "rsi" in strategy_lower and "bb" in strategy_lower:
            self.current_stats.combined_trades += 1
        elif "rsi" in strategy_lower:
            self.current_stats.rsi_trades += 1
        elif "bb" in strategy_lower or "bollinger" in strategy_lower:
            self.current_stats.bb_trades += 1
        
        self._save_stats()
        
        profit_emoji = "📈" if profit >= 0 else "📉"
        logger.info(
            f"📝 거래 기록: ₩{amount:,.0f} | "
            f"{profit_emoji} ₩{profit:+,.0f} | "
            f"일일: {self.current_stats.total_trades}/{self.MAX_DAILY_TRADES}회, "
            f"₩{self.current_stats.total_profit:+,.0f}"
        )
    
    def get_daily_stats(self) -> DailyStats:
        """일일 통계 반환"""
        return self.current_stats
    
    def get_remaining_capacity(self) -> Dict:
        """남은 거래 용량 확인"""
        can_trade, reason = self.can_trade()
        
        win_rate = 0.0
        if self.current_stats.total_trades > 0:
            win_rate = self.current_stats.win_count / self.current_stats.total_trades
        
        return {
            'can_trade': can_trade,
            'reason': reason,
            'remaining_trades': max(0, self.MAX_DAILY_TRADES - self.current_stats.total_trades),
            'remaining_loss_capacity': max(0, self.MAX_DAILY_LOSS + self.current_stats.total_profit),
            'daily_profit': self.current_stats.total_profit,
            'win_rate': win_rate
        }
    
    def emergency_stop(self, reason: str):
        """긴급 거래 중지"""
        logger.critical(f"🚨 긴급 중지: {reason}")
        
        # 거래 횟수를 최대로 설정하여 추가 거래 방지
        self.current_stats.total_trades = self.MAX_DAILY_TRADES
        self._save_stats()


# Test
if __name__ == "__main__":
    print("=== Risk Manager Test ===\n")
    
    rm = RiskManager()
    
    # 거래 가능 확인
    can_trade, reason = rm.can_trade(10000)
    print(f"거래 가능: {can_trade} - {reason}")
    
    # 거래 기록 테스트
    for i in range(3):
        can_trade, reason = rm.can_trade(10000)
        print(f"\n거래 {i+1}: {can_trade} - {reason}")
        
        if can_trade:
            profit = 500 if i % 2 == 0 else -300
            rm.record_trade(10000, profit, strategy="RSI")
        
        print(rm.get_remaining_capacity())
