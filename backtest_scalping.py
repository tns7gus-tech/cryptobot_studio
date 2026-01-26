"""
CryptoBot Studio - Orderbook Scalping Backtest
오더북 스캘핑 전략 백테스트 (시뮬레이션)

Note: 실제 오더북 히스토리는 제공되지 않으므로
1분봉 데이터를 사용하여 가격 변동 기반 시뮬레이션을 수행합니다.
"""
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional
import pytz

KST = pytz.timezone('Asia/Seoul')


@dataclass
class Trade:
    """거래 기록"""
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    amount: float  # KRW
    profit_rate: Optional[float]  # %
    profit: Optional[float]  # KRW
    exit_reason: str  # "익절", "손절", "보유중"


class OrderbookScalpingBacktest:
    """오더북 스캘핑 백테스트"""
    
    def __init__(
        self,
        symbol: str = "KRW-ETH",
        trade_amount: float = 10000,
        take_profit: float = 0.35,  # %
        stop_loss: float = 0.5,     # %
        fee_rate: float = 0.05      # % (편도)
    ):
        self.symbol = symbol
        self.trade_amount = trade_amount
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.fee_rate = fee_rate
        
        self.trades: List[Trade] = []
        self.in_position = False
        self.entry_price = 0.0
        self.entry_time = None
    
    def simulate_orderbook_signal(self, df: pd.DataFrame, idx: int) -> bool:
        """
        오더북 매수 신호 시뮬레이션
        
        실제 오더북 데이터가 없으므로, 다음 조건으로 시뮬레이션:
        - 거래량이 평균의 1.5배 이상
        - 직전 캔들이 양봉 (매수 우세 추정)
        """
        if idx < 20:
            return False
        
        current = df.iloc[idx]
        prev = df.iloc[idx - 1]
        
        # 평균 거래량 대비 현재 거래량
        avg_volume = df['volume'].iloc[idx-20:idx].mean()
        volume_ratio = current['volume'] / avg_volume if avg_volume > 0 else 0
        
        # 시뮬레이션 조건: 거래량 급증 + 양봉
        is_bullish = current['close'] > current['open']
        is_volume_spike = volume_ratio >= 1.5
        
        return is_bullish and is_volume_spike
    
    def run_backtest(self, df: pd.DataFrame) -> dict:
        """백테스트 실행"""
        self.trades = []
        self.in_position = False
        
        for idx in range(len(df)):
            current = df.iloc[idx]
            current_price = current['close']
            current_time = current.name
            
            if self.in_position:
                # 포지션 보유 중 - 익절/손절 체크
                profit_rate = ((current_price - self.entry_price) / self.entry_price) * 100
                
                # 익절
                if profit_rate >= self.take_profit:
                    self._close_position(current_time, current_price, profit_rate, "익절")
                # 손절
                elif profit_rate <= -self.stop_loss:
                    self._close_position(current_time, current_price, profit_rate, "손절")
            else:
                # 포지션 없음 - 진입 조건 체크
                if self.simulate_orderbook_signal(df, idx):
                    self._open_position(current_time, current_price)
        
        # 마지막 포지션 청산 (백테스트 종료)
        if self.in_position:
            last = df.iloc[-1]
            profit_rate = ((last['close'] - self.entry_price) / self.entry_price) * 100
            self._close_position(last.name, last['close'], profit_rate, "백테스트종료")
        
        return self._calculate_results()
    
    def _open_position(self, time: datetime, price: float):
        """포지션 진입"""
        self.in_position = True
        self.entry_price = price
        self.entry_time = time
    
    def _close_position(self, time: datetime, price: float, profit_rate: float, reason: str):
        """포지션 청산"""
        # 수수료 적용 (왕복)
        net_profit_rate = profit_rate - (self.fee_rate * 2)
        profit = self.trade_amount * (net_profit_rate / 100)
        
        trade = Trade(
            entry_time=self.entry_time,
            exit_time=time,
            entry_price=self.entry_price,
            exit_price=price,
            amount=self.trade_amount,
            profit_rate=net_profit_rate,
            profit=profit,
            exit_reason=reason
        )
        self.trades.append(trade)
        
        self.in_position = False
        self.entry_price = 0.0
        self.entry_time = None
    
    def _calculate_results(self) -> dict:
        """결과 계산"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_trades': 0,
                'lose_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'total_profit_rate': 0,
                'avg_profit_rate': 0,
                'max_profit': 0,
                'max_loss': 0
            }
        
        total_profit = sum(t.profit for t in self.trades if t.profit)
        profits = [t.profit_rate for t in self.trades if t.profit_rate is not None]
        
        win_trades = len([p for p in profits if p > 0])
        lose_trades = len([p for p in profits if p < 0])
        
        return {
            'total_trades': len(self.trades),
            'win_trades': win_trades,
            'lose_trades': lose_trades,
            'win_rate': (win_trades / len(self.trades) * 100) if self.trades else 0,
            'total_profit': total_profit,
            'total_profit_rate': (total_profit / self.trade_amount * 100) if self.trade_amount else 0,
            'avg_profit_rate': sum(profits) / len(profits) if profits else 0,
            'max_profit': max(profits) if profits else 0,
            'max_loss': min(profits) if profits else 0
        }
    
    def print_results(self, results: dict):
        """결과 출력"""
        print("\n" + "=" * 60)
        print(f"📊 오더북 스캘핑 백테스트 결과 ({self.symbol})")
        print("=" * 60)
        print(f"\n💰 설정:")
        print(f"   - 1회 거래금액: ₩{self.trade_amount:,.0f}")
        print(f"   - 익절: +{self.take_profit}%")
        print(f"   - 손절: -{self.stop_loss}%")
        print(f"   - 수수료: {self.fee_rate}% (편도)")
        
        print(f"\n📈 거래 결과:")
        print(f"   - 총 거래 횟수: {results['total_trades']}회")
        print(f"   - 승리: {results['win_trades']}회")
        print(f"   - 패배: {results['lose_trades']}회")
        print(f"   - 승률: {results['win_rate']:.1f}%")
        
        print(f"\n💵 수익:")
        print(f"   - 총 수익: ₩{results['total_profit']:,.0f}")
        print(f"   - 총 수익률: {results['total_profit_rate']:.2f}%")
        print(f"   - 평균 수익률: {results['avg_profit_rate']:.2f}%")
        print(f"   - 최대 수익: +{results['max_profit']:.2f}%")
        print(f"   - 최대 손실: {results['max_loss']:.2f}%")
        
        if self.trades:
            print(f"\n📋 최근 거래 내역 (최대 10건):")
            for trade in self.trades[-10:]:
                emoji = "🟢" if (trade.profit_rate and trade.profit_rate > 0) else "🔴"
                print(f"   {emoji} {trade.entry_time.strftime('%H:%M')} → {trade.exit_time.strftime('%H:%M') if trade.exit_time else 'N/A'}: "
                      f"₩{trade.entry_price:,.0f} → ₩{trade.exit_price:,.0f} ({trade.profit_rate:+.2f}%) [{trade.exit_reason}]")
        
        print("\n" + "=" * 60)


def main():
    """백테스트 실행"""
    print("🔄 데이터 로딩 및 백테스트 시작...")
    
    # 테스트할 종목 리스트 (변동성 큰 것과 안정적인 것 섞어서)
    symbols = ["KRW-BTC", "KRW-XRP", "KRW-DOGE", "KRW-SOL"]
    
    total_profit_all = 0
    total_trades_all = 0
    wins_all = 0
    
    for symbol in symbols:
        try:
            # 최근 24시간 (60분봉 * 24) or 1분봉 * 1440
            # 스캘핑이므로 1분봉 4시간(240개) 정도 테스트
            df = pyupbit.get_ohlcv(symbol, interval="minute1", count=240)
            
            if df is None or len(df) == 0:
                print(f"❌ {symbol} 데이터 조회 실패")
                continue
            
            # 시간대 변환
            df.index = df.index.tz_localize('UTC').tz_convert(KST)
            
            # 백테스트 실행 (설정값 업데이트: 익절 1.5%, 손절 1.0%)
            backtest = OrderbookScalpingBacktest(
                symbol=symbol,
                trade_amount=10000,
                take_profit=1.5,
                stop_loss=1.0,
                fee_rate=0.05
            )
            
            results = backtest.run_backtest(df)
            backtest.print_results(results)
            
            total_profit_all += results['total_profit']
            total_trades_all += results['total_trades']
            wins_all += results['win_trades']
            
        except Exception as e:
            print(f"❌ {symbol} 에러: {e}")
            
    print("\n" + "*" * 60)
    print(f"📊 [종합 결과] 오늘 예상 하루 수익 (4시간 데이터 기준)")
    print(f"   - 총 거래: {total_trades_all}회")
    win_rate_all = (wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    print(f"   - 평균 승률: {win_rate_all:.1f}%")
    
    # 단순 4시간 수익 * 6 = 하루 예상 수익 (단순 계산)
    daily_proj = total_profit_all * 6
    print(f"   - 4시간 실현 수익: ₩{total_profit_all:,.0f}")
    print(f"   - 하루 예상 수익 ({len(symbols)}종목 운용 시): ₩{daily_proj:,.0f}")
    print("*" * 60)
    print("※ 주의: 과거 오더북 데이터 부재로 OHLCV 변동성 기반 시뮬레이션 결과입니다.")
    print("        실제 지정가 체결 및 갭 체크가 적용되면 승률이 더 높을 수 있습니다.")


if __name__ == "__main__":
    main()
