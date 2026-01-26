"""
CryptoBot Studio - Optimized Monthly Backtest (V2)
포지션 확대 + ICT 조건 완화 버전
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


class OptimizedBacktester:
    """
    최적화된 백테스터 V2
    
    변경사항:
    - ICT Confluence: 80점 → 50점 (완화)
    - ICT 포지션: 10% → 30%
    - 추세 포지션: 3% → 15%
    """
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ["KRW-ETH", "KRW-SOL"]
        
        # 공격적 포지션 설정
        self.ict_position_ratio = 0.30   # 30% (기존 10%)
        self.trend_position_ratio = 0.15  # 15% (기존 3%)
        
        # ICT 조건 완화
        self.ict_confluence_threshold = 50  # 50점 (기존 80점)
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def simulate_ict(self, df: pd.DataFrame) -> List[Dict]:
        """ICT 시뮬레이션 (완화된 조건)"""
        trades = []
        take_profit, stop_loss = 2.0, 1.0
        
        i = 30
        while i < len(df) - 1:
            window = df.iloc[max(0, i-30):i+1]
            
            ob = detect_order_block(window)
            fvg = detect_fvg(window, min_gap_percent=0.03)  # 0.05 → 0.03 완화
            lp = detect_liquidity_pool(window)
            
            score = 0
            if ob and ob.found: score += 30
            if fvg and fvg.found: score += 30
            if lp and lp.found: score += 20
            
            # 가격이 영역 내에 있으면 추가 점수
            current_price = df.iloc[i]['close']
            if ob and ob.found:
                if ob.zone_bottom <= current_price <= ob.zone_top:
                    score += 10
            
            direction = "BULLISH"
            if ob and ob.found: direction = ob.direction
            elif fvg and fvg.found: direction = fvg.direction
            
            # 50점 이상 (기존 80점)
            if score >= self.ict_confluence_threshold and direction == "BULLISH":
                entry = df.iloc[i]['close']
                
                for j in range(i + 1, min(i + 24, len(df))):
                    current = df.iloc[j]['close']
                    profit = ((current - entry) / entry) * 100
                    
                    if profit >= take_profit:
                        trades.append({"profit": profit, "win": True, "strategy": "ICT"})
                        i = j + 1
                        break
                    if profit <= -stop_loss:
                        trades.append({"profit": profit, "win": False, "strategy": "ICT"})
                        i = j + 1
                        break
                else:
                    exit_idx = min(i + 24, len(df) - 1)
                    profit = ((df.iloc[exit_idx]['close'] - entry) / entry) * 100
                    trades.append({"profit": profit, "win": profit > 0, "strategy": "ICT"})
                    i = exit_idx + 1
                    continue
            i += 1
        
        return trades
    
    def simulate_trend(self, df: pd.DataFrame) -> List[Dict]:
        """추세 시뮬레이션 (기존과 동일)"""
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
                        trades.append({"profit": profit, "win": True, "strategy": "TREND"})
                        i = j + 3
                        break
                    if profit <= -stop_loss:
                        trades.append({"profit": profit, "win": False, "strategy": "TREND"})
                        i = j + 3
                        break
                else:
                    i += 1
                    continue
            else:
                i += 1
        
        return trades
    
    def get_monthly_data(self, symbol: str, year: int, month: int, interval: str, count: int) -> pd.DataFrame:
        try:
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count, to=end_date.strftime("%Y%m%d"))
            time.sleep(0.2)
            return df
        except Exception as e:
            print(f"   ⚠️ {symbol} 데이터 조회 실패: {e}")
            return None
    
    def run_monthly_backtest(self, year: int, month: int) -> Dict:
        all_ict_trades = []
        all_trend_trades = []
        
        for symbol in self.symbols:
            df_1h = self.get_monthly_data(symbol, year, month, "minute60", 800)
            if df_1h is not None and len(df_1h) > 50:
                ict = self.simulate_ict(df_1h)
                all_ict_trades.extend(ict)
            
            df_5m = self.get_monthly_data(symbol, year, month, "minute5", 2000)
            if df_5m is not None and len(df_5m) > 50:
                trend = self.simulate_trend(df_5m)
                all_trend_trades.extend(trend)
        
        # 수익률 계산 (확대된 포지션)
        ict_profit = sum(t["profit"] * self.ict_position_ratio for t in all_ict_trades)
        trend_profit = sum(t["profit"] * self.trend_position_ratio for t in all_trend_trades)
        total_profit = ict_profit + trend_profit
        
        total_trades = len(all_ict_trades) + len(all_trend_trades)
        wins = len([t for t in all_ict_trades + all_trend_trades if t["win"]])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
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
    print("🚀 CryptoBot Studio - 최적화 백테스트 V2")
    print("   ICT: Confluence 50점+, 포지션 30%")
    print("   추세: 포지션 15%")
    print("=" * 70)
    print()
    
    backtester = OptimizedBacktester(symbols=["KRW-ETH", "KRW-SOL"])
    
    results = []
    
    # 2025년 1월 ~ 12월
    for month in range(1, 13):
        print(f"📊 2025년 {month:02d}월 분석 중...")
        result = backtester.run_monthly_backtest(2025, month)
        results.append(result)
        print(f"   ICT: {result['ict_trades']}회, 추세: {result['trend_trades']}회, 승률: {result['win_rate']:.1f}%, 수익: {result['total_profit']:.2f}%")
    
    # 2026년 1월
    print(f"📊 2026년 01월 분석 중...")
    result = backtester.run_monthly_backtest(2026, 1)
    results.append(result)
    print(f"   ICT: {result['ict_trades']}회, 추세: {result['trend_trades']}회, 승률: {result['win_rate']:.1f}%, 수익: {result['total_profit']:.2f}%")
    
    # 결과 출력
    print()
    print("=" * 80)
    print("📈 최적화 백테스트 V2 결과")
    print("=" * 80)
    print()
    print(f"{'기간':<10} {'ICT거래':<8} {'추세거래':<8} {'총거래':<8} {'승률':<8} {'ICT수익':<10} {'추세수익':<10} {'총수익':<10} {'일평균':<10}")
    print("-" * 90)
    
    for r in results:
        period = f"{r['year']}.{r['month']:02d}"
        print(f"{period:<10} {r['ict_trades']:<8} {r['trend_trades']:<8} {r['total_trades']:<8} "
              f"{r['win_rate']:.1f}%{'':<3} {r['ict_profit']:>+.2f}%{'':<2} {r['trend_profit']:>+.2f}%{'':<2} "
              f"{r['total_profit']:>+.2f}%{'':<2} {r['daily_avg']:>+.3f}%")
    
    print("-" * 90)
    
    # 총합
    total_ict = sum(r['ict_trades'] for r in results)
    total_trend = sum(r['trend_trades'] for r in results)
    total_trades = sum(r['total_trades'] for r in results)
    total_ict_profit = sum(r['ict_profit'] for r in results)
    total_trend_profit = sum(r['trend_profit'] for r in results)
    total_profit = sum(r['total_profit'] for r in results)
    avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
    avg_daily = sum(r['daily_avg'] for r in results) / len(results)
    
    print(f"{'합계':<10} {total_ict:<8} {total_trend:<8} {total_trades:<8} "
          f"{avg_win_rate:.1f}%{'':<3} {total_ict_profit:>+.2f}%{'':<2} {total_trend_profit:>+.2f}%{'':<2} "
          f"{total_profit:>+.2f}%{'':<2} {avg_daily:>+.3f}%")
    
    print()
    print("=" * 80)
    
    # 1% 달성 분석
    target_months = [r for r in results if r['daily_avg'] >= 1.0]
    partial_months = [r for r in results if 0.5 <= r['daily_avg'] < 1.0]
    
    print()
    print("🎯 일일 1% 목표 달성 분석:")
    print(f"   ✅ 목표 달성 월 (일 1%+): {len(target_months)}개월")
    for m in target_months:
        print(f"      - {m['year']}.{m['month']:02d}: {m['daily_avg']:.3f}%/일")
    
    print(f"   🔶 부분 달성 월 (일 0.5~1%): {len(partial_months)}개월")
    print(f"   ❌ 미달 월 (일 <0.5%): {len(results) - len(target_months) - len(partial_months)}개월")
    print()
    
    if avg_daily >= 1.0:
        print(f"🎉 평균 일일 수익률: {avg_daily:.3f}% - 목표 달성!")
    elif avg_daily >= 0.5:
        print(f"🔶 평균 일일 수익률: {avg_daily:.3f}% - 부분 달성 (목표의 {avg_daily/1.0*100:.0f}%)")
    else:
        print(f"⚠️ 평균 일일 수익률: {avg_daily:.3f}% - 미달 (목표의 {avg_daily/1.0*100:.0f}%)")
    
    # 연간 복리 수익 계산
    annual_return = total_profit
    print(f"\n📊 13개월 총 수익률: {annual_return:.2f}%")
    print(f"   초기 100만원 → {100 * (1 + annual_return/100):,.0f}만원")


if __name__ == "__main__":
    main()
