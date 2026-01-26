"""
CryptoBot Studio - Extended Monthly Backtest
2025년 1월~12월 + 2026년 1월 월별 백테스트
"""
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from indicators import detect_order_block, detect_fvg, detect_liquidity_pool


class MonthlyBacktester:
    """월별 백테스트"""
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ["KRW-ETH", "KRW-SOL"]
        self.ict_position_ratio = 0.10
        self.trend_position_ratio = 0.03
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def simulate_ict(self, df: pd.DataFrame) -> List[Dict]:
        """ICT 시뮬레이션 (1시간봉)"""
        trades = []
        take_profit, stop_loss = 2.0, 1.0
        
        i = 30
        while i < len(df) - 1:
            window = df.iloc[max(0, i-30):i+1]
            
            ob = detect_order_block(window)
            fvg = detect_fvg(window, min_gap_percent=0.05)
            lp = detect_liquidity_pool(window)
            
            score = 0
            if ob and ob.found: score += 30
            if fvg and fvg.found: score += 30
            if lp and lp.found: score += 20
            
            direction = "BULLISH"
            if ob and ob.found: direction = ob.direction
            elif fvg and fvg.found: direction = fvg.direction
            
            if score >= 80 and direction == "BULLISH":
                entry = df.iloc[i]['close']
                
                for j in range(i + 1, min(i + 24, len(df))):
                    current = df.iloc[j]['close']
                    profit = ((current - entry) / entry) * 100
                    
                    if profit >= take_profit:
                        trades.append({"profit": profit, "win": True})
                        i = j + 1
                        break
                    if profit <= -stop_loss:
                        trades.append({"profit": profit, "win": False})
                        i = j + 1
                        break
                else:
                    exit_idx = min(i + 24, len(df) - 1)
                    profit = ((df.iloc[exit_idx]['close'] - entry) / entry) * 100
                    trades.append({"profit": profit, "win": profit > 0})
                    i = exit_idx + 1
                    continue
            i += 1
        
        return trades
    
    def simulate_trend(self, df: pd.DataFrame) -> List[Dict]:
        """추세 시뮬레이션 (5분봉)"""
        trades = []
        take_profit, stop_loss = 0.3, 0.5
        
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df, 14)
        df['ema_fast'] = self.calculate_ema(df, 12)
        df['ema_slow'] = self.calculate_ema(df, 26)
        
        i = 30
        while i < len(df) - 1:
            if pd.isna(df['rsi'].iloc[i]):
                i += 1
                continue
            
            rsi = df['rsi'].iloc[i]
            ema_fast = df['ema_fast'].iloc[i]
            ema_slow = df['ema_slow'].iloc[i]
            prev_ema_fast = df['ema_fast'].iloc[i-1]
            prev_ema_slow = df['ema_slow'].iloc[i-1]
            
            golden = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
            bullish = ema_fast > ema_slow and 30 < rsi < 50
            
            if golden or bullish:
                entry = df.iloc[i]['close']
                
                for j in range(i + 1, min(i + 12, len(df))):
                    current = df.iloc[j]['close']
                    profit = ((current - entry) / entry) * 100
                    
                    if profit >= take_profit:
                        trades.append({"profit": profit, "win": True})
                        i = j + 3
                        break
                    if profit <= -stop_loss:
                        trades.append({"profit": profit, "win": False})
                        i = j + 3
                        break
                else:
                    i += 1
                    continue
            else:
                i += 1
        
        return trades
    
    def get_monthly_data(self, symbol: str, year: int, month: int, interval: str, count: int) -> pd.DataFrame:
        """월별 데이터 조회"""
        try:
            # 해당 월의 마지막 날짜 계산
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            # pyupbit은 to 파라미터로 과거 데이터 조회 가능
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count, to=end_date.strftime("%Y%m%d"))
            time.sleep(0.2)  # Rate limit
            return df
        except Exception as e:
            print(f"   ⚠️ {symbol} 데이터 조회 실패: {e}")
            return None
    
    def run_monthly_backtest(self, year: int, month: int) -> Dict:
        """월별 백테스트"""
        all_ict_trades = []
        all_trend_trades = []
        
        for symbol in self.symbols:
            # 1시간봉 (ICT) - 월 약 720시간
            df_1h = self.get_monthly_data(symbol, year, month, "minute60", 800)
            if df_1h is not None and len(df_1h) > 50:
                ict = self.simulate_ict(df_1h)
                all_ict_trades.extend(ict)
            
            # 5분봉 (추세) - 샘플링 (너무 많으면 속도 문제)
            df_5m = self.get_monthly_data(symbol, year, month, "minute5", 2000)
            if df_5m is not None and len(df_5m) > 50:
                trend = self.simulate_trend(df_5m)
                all_trend_trades.extend(trend)
        
        # 수익률 계산
        ict_profit = sum(t["profit"] * self.ict_position_ratio for t in all_ict_trades)
        trend_profit = sum(t["profit"] * self.trend_position_ratio for t in all_trend_trades)
        total_profit = ict_profit + trend_profit
        
        total_trades = len(all_ict_trades) + len(all_trend_trades)
        wins = len([t for t in all_ict_trades + all_trend_trades if t["win"]])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # 일 평균 수익률 (월 약 30일)
        days_in_month = 30 if month != 2 else 28
        daily_avg = total_profit / days_in_month if days_in_month > 0 else 0
        
        return {
            "year": year,
            "month": month,
            "ict_trades": len(all_ict_trades),
            "trend_trades": len(all_trend_trades),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "ict_profit": ict_profit,
            "trend_profit": trend_profit,
            "total_profit": total_profit,
            "daily_avg": daily_avg
        }


def main():
    print()
    print("=" * 70)
    print("🚀 CryptoBot Studio - 월별 백테스트 (2025년 + 2026년 1월)")
    print("=" * 70)
    print()
    
    backtester = MonthlyBacktester(symbols=["KRW-ETH", "KRW-SOL"])
    
    results = []
    
    # 2025년 1월 ~ 12월
    for month in range(1, 13):
        print(f"📊 2025년 {month:02d}월 분석 중...")
        result = backtester.run_monthly_backtest(2025, month)
        results.append(result)
        print(f"   완료: {result['total_trades']}거래, 승률 {result['win_rate']:.1f}%, 수익 {result['total_profit']:.2f}%")
    
    # 2026년 1월
    print(f"📊 2026년 01월 분석 중...")
    result = backtester.run_monthly_backtest(2026, 1)
    results.append(result)
    print(f"   완료: {result['total_trades']}거래, 승률 {result['win_rate']:.1f}%, 수익 {result['total_profit']:.2f}%")
    
    # 결과 출력
    print()
    print("=" * 70)
    print("📈 월별 백테스트 결과 요약")
    print("=" * 70)
    print()
    print(f"{'기간':<15} {'총거래':<8} {'ICT':<6} {'추세':<6} {'승률':<8} {'ICT수익':<10} {'추세수익':<10} {'총수익':<10} {'일평균':<8}")
    print("-" * 90)
    
    for r in results:
        period = f"{r['year']}.{r['month']:02d}"
        print(f"{period:<15} {r['total_trades']:<8} {r['ict_trades']:<6} {r['trend_trades']:<6} "
              f"{r['win_rate']:.1f}%{'':<4} {r['ict_profit']:>+.2f}%{'':<3} {r['trend_profit']:>+.2f}%{'':<3} "
              f"{r['total_profit']:>+.2f}%{'':<3} {r['daily_avg']:>+.3f}%")
    
    print("-" * 90)
    
    # 총합
    total_trades = sum(r['total_trades'] for r in results)
    total_profit = sum(r['total_profit'] for r in results)
    avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
    total_daily_avg = sum(r['daily_avg'] for r in results) / len(results)
    
    print(f"{'합계/평균':<15} {total_trades:<8} {'-':<6} {'-':<6} "
          f"{avg_win_rate:.1f}%{'':<4} {'-':<10} {'-':<10} "
          f"{total_profit:>+.2f}%{'':<3} {total_daily_avg:>+.3f}%")
    
    print()
    
    # 1% 달성 가능성 평가
    target_achieved_months = [r for r in results if r['daily_avg'] >= 1.0]
    partial_months = [r for r in results if 0.5 <= r['daily_avg'] < 1.0]
    
    print("🎯 일일 1% 목표 달성 분석:")
    print(f"   ✅ 목표 달성 월: {len(target_achieved_months)}개월")
    print(f"   🔶 부분 달성 월 (0.5%+): {len(partial_months)}개월")
    print(f"   ❌ 미달 월: {len(results) - len(target_achieved_months) - len(partial_months)}개월")
    print()
    
    if total_daily_avg >= 1.0:
        print("🎉 평균 일일 수익률 1% 달성 가능!")
    else:
        print(f"⚠️ 평균 일일 수익률: {total_daily_avg:.3f}% (목표 대비 {total_daily_avg/1.0*100:.1f}%)")


if __name__ == "__main__":
    main()
