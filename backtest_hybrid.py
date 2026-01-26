"""
CryptoBot Studio - Hybrid Strategy Backtest
ICT + Trend Following 하이브리드 전략 백테스트
오늘 하루 기준으로 예상 수익률 계산
"""
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict
import sys
import os

# src 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from indicators import detect_order_block, detect_fvg, detect_liquidity_pool


@dataclass
class BacktestTrade:
    """백테스트 거래 기록"""
    symbol: str
    strategy: str  # "ICT" or "TREND"
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    profit_percent: float
    position_size_ratio: float


class HybridBacktester:
    """
    하이브리드 전략 백테스터
    
    시뮬레이션:
    - ICT: 1시간봉 Confluence 80점 이상, 익절 2%, 손절 1%
    - 추세: 5분봉 RSI+EMA, 익절 0.3%, 손절 0.5%
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        initial_capital: float = 100000,
        ict_position_ratio: float = 0.10,   # ICT: 10% (고승률 → 공격적)
        trend_position_ratio: float = 0.03  # 추세: 3% (고빈도 → 중간)
    ):
        self.symbols = symbols or ["KRW-ETH", "KRW-SOL"]
        self.initial_capital = initial_capital
        self.ict_position_ratio = ict_position_ratio
        self.trend_position_ratio = trend_position_ratio
        
        # 거래 기록
        self.trades: List[BacktestTrade] = []
        self.capital = initial_capital
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """EMA 계산"""
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def simulate_ict_trade(self, df: pd.DataFrame, symbol: str) -> List[BacktestTrade]:
        """ICT 거래 시뮬레이션 (1시간봉)"""
        trades = []
        
        take_profit = 2.0
        stop_loss = 1.0
        
        i = 30
        while i < len(df) - 1:
            window = df.iloc[max(0, i-30):i+1]
            
            # ICT 지표 계산
            ob = detect_order_block(window)
            fvg = detect_fvg(window, min_gap_percent=0.05)
            lp = detect_liquidity_pool(window)
            
            score = 0
            if ob and ob.found: score += 30
            if fvg and fvg.found: score += 30
            if lp and lp.found: score += 20
            
            # Confluence 80점 이상 + Bullish
            if score >= 80:
                direction = "BULLISH"
                if ob and ob.found:
                    direction = ob.direction
                elif fvg and fvg.found:
                    direction = fvg.direction
                
                if direction == "BULLISH":
                    entry_price = df.iloc[i]['close']
                    entry_time = str(df.index[i])
                    
                    # 익절/손절 시뮬레이션
                    for j in range(i + 1, min(i + 24, len(df))):  # 최대 24시간
                        current = df.iloc[j]['close']
                        profit = ((current - entry_price) / entry_price) * 100
                        
                        if profit >= take_profit:
                            trades.append(BacktestTrade(
                                symbol=symbol,
                                strategy="ICT",
                                entry_price=entry_price,
                                exit_price=current,
                                entry_time=entry_time,
                                exit_time=str(df.index[j]),
                                profit_percent=profit,
                                position_size_ratio=self.ict_position_ratio
                            ))
                            i = j + 1
                            break
                        
                        if profit <= -stop_loss:
                            trades.append(BacktestTrade(
                                symbol=symbol,
                                strategy="ICT",
                                entry_price=entry_price,
                                exit_price=current,
                                entry_time=entry_time,
                                exit_time=str(df.index[j]),
                                profit_percent=profit,
                                position_size_ratio=self.ict_position_ratio
                            ))
                            i = j + 1
                            break
                    else:
                        # 타임아웃 - 현재가로 청산
                        exit_idx = min(i + 24, len(df) - 1)
                        current = df.iloc[exit_idx]['close']
                        profit = ((current - entry_price) / entry_price) * 100
                        trades.append(BacktestTrade(
                            symbol=symbol,
                            strategy="ICT",
                            entry_price=entry_price,
                            exit_price=current,
                            entry_time=entry_time,
                            exit_time=str(df.index[exit_idx]),
                            profit_percent=profit,
                            position_size_ratio=self.ict_position_ratio
                        ))
                        i = exit_idx + 1
                        continue
            
            i += 1
        
        return trades
    
    def simulate_trend_trade(self, df: pd.DataFrame, symbol: str) -> List[BacktestTrade]:
        """추세추종 거래 시뮬레이션 (5분봉)"""
        trades = []
        
        take_profit = 0.3
        stop_loss = 0.5
        
        # 지표 계산
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df, 14)
        df['ema_fast'] = self.calculate_ema(df, 12)
        df['ema_slow'] = self.calculate_ema(df, 26)
        
        i = 30
        while i < len(df) - 1:
            if pd.isna(df['rsi'].iloc[i]):
                i += 1
                continue
            
            current_rsi = df['rsi'].iloc[i]
            ema_fast = df['ema_fast'].iloc[i]
            ema_slow = df['ema_slow'].iloc[i]
            prev_ema_fast = df['ema_fast'].iloc[i-1]
            prev_ema_slow = df['ema_slow'].iloc[i-1]
            
            # 골든크로스 + RSI < 50
            golden_cross = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
            bullish = ema_fast > ema_slow and current_rsi < 50 and current_rsi > 30
            
            if golden_cross or bullish:
                entry_price = df.iloc[i]['close']
                entry_time = str(df.index[i])
                
                # 익절/손절 시뮬레이션 (5분 타임아웃)
                for j in range(i + 1, min(i + 12, len(df))):  # 최대 1시간 (12 * 5분)
                    current = df.iloc[j]['close']
                    profit = ((current - entry_price) / entry_price) * 100
                    
                    if profit >= take_profit:
                        trades.append(BacktestTrade(
                            symbol=symbol,
                            strategy="TREND",
                            entry_price=entry_price,
                            exit_price=current,
                            entry_time=entry_time,
                            exit_time=str(df.index[j]),
                            profit_percent=profit,
                            position_size_ratio=self.trend_position_ratio
                        ))
                        i = j + 3  # 쿨다운
                        break
                    
                    if profit <= -stop_loss:
                        trades.append(BacktestTrade(
                            symbol=symbol,
                            strategy="TREND",
                            entry_price=entry_price,
                            exit_price=current,
                            entry_time=entry_time,
                            exit_time=str(df.index[j]),
                            profit_percent=profit,
                            position_size_ratio=self.trend_position_ratio
                        ))
                        i = j + 3
                        break
                else:
                    i += 1
                    continue
            else:
                i += 1
        
        return trades
    
    def run_backtest(self, hours: int = 24):
        """백테스트 실행"""
        print(f"🔄 하이브리드 전략 백테스트 시작...")
        print(f"   대상: {', '.join(self.symbols)}")
        print(f"   기간: 최근 {hours}시간")
        print(f"   초기 자본: ₩{self.initial_capital:,.0f}")
        print()
        
        all_trades = []
        
        for symbol in self.symbols:
            print(f"📊 {symbol} 분석 중...")
            
            # 1시간봉 데이터 (ICT용)
            df_1h = pyupbit.get_ohlcv(symbol, interval="minute60", count=hours + 50)
            if df_1h is not None:
                ict_trades = self.simulate_ict_trade(df_1h, symbol)
                all_trades.extend(ict_trades)
                print(f"   ICT 거래: {len(ict_trades)}회")
            
            # 5분봉 데이터 (추세용)
            df_5m = pyupbit.get_ohlcv(symbol, interval="minute5", count=hours * 12 + 50)
            if df_5m is not None:
                trend_trades = self.simulate_trend_trade(df_5m, symbol)
                all_trades.extend(trend_trades)
                print(f"   추세 거래: {len(trend_trades)}회")
        
        self.trades = all_trades
        return self.calculate_results()
    
    def calculate_results(self) -> Dict:
        """결과 계산"""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_profit_percent": 0,
                "net_profit_krw": 0
            }
        
        # 전략별 분리
        ict_trades = [t for t in self.trades if t.strategy == "ICT"]
        trend_trades = [t for t in self.trades if t.strategy == "TREND"]
        
        # 수익률 계산 (포지션 크기 가중)
        total_weighted_profit = 0
        for trade in self.trades:
            weighted_profit = trade.profit_percent * trade.position_size_ratio
            total_weighted_profit += weighted_profit
        
        # 승률
        wins = [t for t in self.trades if t.profit_percent > 0]
        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        
        # 순이익
        net_profit_krw = self.initial_capital * (total_weighted_profit / 100)
        
        results = {
            "total_trades": len(self.trades),
            "ict_trades": len(ict_trades),
            "trend_trades": len(trend_trades),
            "win_count": len(wins),
            "loss_count": len(self.trades) - len(wins),
            "win_rate": win_rate,
            "total_profit_percent": total_weighted_profit,
            "net_profit_krw": net_profit_krw,
            "ict_profit": sum(t.profit_percent * t.position_size_ratio for t in ict_trades),
            "trend_profit": sum(t.profit_percent * t.position_size_ratio for t in trend_trades)
        }
        
        return results
    
    def print_results(self, results: Dict):
        """결과 출력"""
        print()
        print("=" * 60)
        print("📊 하이브리드 전략 백테스트 결과")
        print("=" * 60)
        print()
        
        print(f"📈 거래 통계:")
        print(f"   총 거래: {results['total_trades']}회")
        print(f"   - ICT 거래: {results['ict_trades']}회")
        print(f"   - 추세 거래: {results['trend_trades']}회")
        print(f"   승리: {results['win_count']}회 / 패배: {results['loss_count']}회")
        print(f"   승률: {results['win_rate']:.1f}%")
        print()
        
        print(f"💰 수익률:")
        print(f"   ICT 수익: {results['ict_profit']:.3f}%")
        print(f"   추세 수익: {results['trend_profit']:.3f}%")
        print(f"   총 수익: {results['total_profit_percent']:.3f}%")
        print()
        
        print(f"💵 예상 순이익:")
        print(f"   ₩{results['net_profit_krw']:,.0f}")
        print()
        
        # 일일 1% 달성 여부
        if results['total_profit_percent'] >= 1.0:
            print("🎉 일일 1% 목표 달성! ✅")
        else:
            needed = 1.0 - results['total_profit_percent']
            print(f"⚠️ 목표까지 {needed:.3f}% 부족")
        
        print("=" * 60)
        
        # 거래 상세
        if self.trades:
            print("\n📋 거래 상세 (최근 10건):")
            for trade in self.trades[-10:]:
                emoji = "✅" if trade.profit_percent > 0 else "❌"
                print(f"   {emoji} [{trade.strategy}] {trade.symbol}: {trade.profit_percent:+.2f}% (₩{trade.entry_price:,.0f} → ₩{trade.exit_price:,.0f})")


def main():
    """메인 실행"""
    print()
    print("🚀 CryptoBot Studio - Hybrid Strategy Backtest")
    print("   ICT (고승률) + Trend Following (고빈도)")
    print()
    
    backtester = HybridBacktester(
        symbols=["KRW-ETH", "KRW-SOL"],
        initial_capital=100000
    )
    
    # 최근 24시간 백테스트
    results = backtester.run_backtest(hours=24)
    backtester.print_results(results)
    
    return results


if __name__ == "__main__":
    main()
