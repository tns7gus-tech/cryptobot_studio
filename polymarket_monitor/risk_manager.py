"""
Risk Management System
Controls betting frequency, amount, and daily loss limits
"""
import json
from datetime import datetime, date
from typing import Dict, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from loguru import logger


@dataclass
class DailyStats:
    """일일 통계"""
    date: str
    total_bets: int
    total_wagered: float
    total_profit: float
    win_count: int
    loss_count: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


class RiskManager:
    """
    리스크 관리 시스템
    - 일일 베팅 횟수 제한
    - 1회 베팅 금액 제한
    - 일일 손실 한도
    """
    
    # Limits
    MAX_BET_PER_TRADE = 50      # 1회 최대 $50
    MAX_DAILY_BETS = 5          # 하루 최대 5회
    MAX_DAILY_LOSS = 200        # 일일 손실 한도 $200
    
    def __init__(self, stats_file: str = "data/daily_stats.json"):
        self.stats_file = Path(stats_file)
        self.stats_file.parent.mkdir(exist_ok=True)
        
        self.current_stats = self._load_today_stats()
        
        logger.info("📊 Risk Manager initialized")
        logger.info(f"Max bet: ${self.MAX_BET_PER_TRADE}")
        logger.info(f"Max daily bets: {self.MAX_DAILY_BETS}")
        logger.info(f"Max daily loss: ${self.MAX_DAILY_LOSS}")
    
    def _load_today_stats(self) -> DailyStats:
        """Load or create today's stats"""
        today = date.today().isoformat()
        
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                
                # Check if it's today's data
                if data.get('date') == today:
                    return DailyStats(**data)
            except Exception as e:
                logger.error(f"Error loading stats: {e}")
        
        # Create new stats for today
        return DailyStats(
            date=today,
            total_bets=0,
            total_wagered=0.0,
            total_profit=0.0,
            win_count=0,
            loss_count=0
        )
    
    def _save_stats(self):
        """Save current stats to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.current_stats.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def can_trade(self, amount: float = None) -> Tuple[bool, str]:
        """
        Check if trading is allowed
        
        Args:
            amount: Proposed bet amount (optional)
            
        Returns:
            (can_trade, reason)
        """
        # Check if new day (auto-reset)
        today = date.today().isoformat()
        if self.current_stats.date != today:
            logger.info("📅 New day - resetting limits")
            self.current_stats = DailyStats(
                date=today,
                total_bets=0,
                total_wagered=0.0,
                total_profit=0.0,
                win_count=0,
                loss_count=0
            )
            self._save_stats()
        
        # Check daily bet count
        if self.current_stats.total_bets >= self.MAX_DAILY_BETS:
            return False, f"Daily bet limit reached ({self.MAX_DAILY_BETS})"
        
        # Check daily loss
        if self.current_stats.total_profit < -self.MAX_DAILY_LOSS:
            return False, f"Daily loss limit exceeded (${abs(self.current_stats.total_profit):.2f})"
        
        # Check bet amount
        if amount:
            if amount > self.MAX_BET_PER_TRADE:
                return False, f"Bet amount ${amount:.2f} exceeds limit ${self.MAX_BET_PER_TRADE}"
            
            # Check if this bet would exceed daily loss limit
            potential_loss = self.current_stats.total_profit - amount
            if potential_loss < -self.MAX_DAILY_LOSS:
                return False, f"Potential loss would exceed daily limit"
        
        return True, "OK"
    
    def record_trade(self, amount: float, profit: float, won: bool = None):
        """
        Record a trade
        
        Args:
            amount: Bet amount
            profit: Profit/loss (positive = profit, negative = loss)
            won: Whether the bet won (optional, inferred from profit if None)
        """
        self.current_stats.total_bets += 1
        self.current_stats.total_wagered += amount
        self.current_stats.total_profit += profit
        
        if won is None:
            won = profit > 0
        
        if won:
            self.current_stats.win_count += 1
        else:
            self.current_stats.loss_count += 1
        
        self._save_stats()
        
        logger.info(
            f"📝 Trade recorded: ${amount:.2f} | "
            f"Profit: ${profit:+.2f} | "
            f"Daily: {self.current_stats.total_bets}/{self.MAX_DAILY_BETS} bets, "
            f"${self.current_stats.total_profit:+.2f} P/L"
        )
    
    def get_daily_stats(self) -> DailyStats:
        """Get current daily stats"""
        return self.current_stats
    
    def get_remaining_capacity(self) -> Dict:
        """Get remaining trading capacity"""
        can_trade, reason = self.can_trade()
        
        return {
            'can_trade': can_trade,
            'reason': reason,
            'remaining_bets': max(0, self.MAX_DAILY_BETS - self.current_stats.total_bets),
            'remaining_loss_capacity': max(0, self.MAX_DAILY_LOSS + self.current_stats.total_profit),
            'daily_profit': self.current_stats.total_profit,
            'win_rate': (
                self.current_stats.win_count / self.current_stats.total_bets
                if self.current_stats.total_bets > 0
                else 0.0
            )
        }
    
    def emergency_stop(self, reason: str):
        """Emergency stop all trading"""
        logger.critical(f"🚨 EMERGENCY STOP: {reason}")
        
        # Set bets to max to prevent further trading
        self.current_stats.total_bets = self.MAX_DAILY_BETS
        self._save_stats()


# Test
if __name__ == "__main__":
    rm = RiskManager()
    
    # Test trading
    for i in range(6):
        can_trade, reason = rm.can_trade(50)
        print(f"Trade {i+1}: {can_trade} - {reason}")
        
        if can_trade:
            # Simulate trade
            profit = 10 if i % 2 == 0 else -50
            rm.record_trade(50, profit)
        
        print(rm.get_remaining_capacity())
        print()
