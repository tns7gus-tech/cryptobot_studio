"""
CryptoBot Studio - Auto Trading Engine (Hybrid Strategy)
ICT + Trend Following 하이브리드 전략으로 매일 1% 목표
"""
from typing import Optional, Literal, Dict, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from config import settings
from upbit_client import UpbitClient, OrderResult
from hybrid_strategy import HybridStrategy, HybridSignal
from telegram_notifier import TelegramNotifier
from risk_manager import RiskManager


@dataclass
class TradeResult:
    """거래 결과"""
    success: bool
    action: str
    symbol: str
    order: Optional[OrderResult]
    signal: Optional[HybridSignal]
    price: Optional[float]
    amount: Optional[float]
    volume: Optional[float]
    strategy_type: str = "UNKNOWN"
    error: Optional[str] = None
    
    def __str__(self):
        if self.success:
            price_str = f"₩{self.price:,.0f}" if self.price else "N/A"
            return f"✅ [{self.strategy_type}] {self.symbol} {self.action}: {price_str}"
        return f"❌ [{self.strategy_type}] {self.symbol} {self.action}: {self.error}"


@dataclass
class PositionInfo:
    """포지션 정보"""
    in_position: bool
    entry_price: float
    balance: float
    strategy_type: str  # "ICT" or "TREND"
    entry_time: datetime = None


class AutoTrader:
    """
    자동매매 엔진 (하이브리드 전략)
    
    동작:
    - 10분마다: 1시간봉 ICT 신호 확인 (고승률)
    - 5분마다: 5분봉 추세 신호 확인 (고빈도)
    - 일일 1% 달성 시 보수적 모드
    
    대상: ETH, USDT, SOL (BTC 제외 - DCA)
    """
    
    def __init__(
        self,
        mode: Literal["semi", "full"] = None,
        check_interval: int = 300  # 5분 기본
    ):
        self.mode = mode or settings.bot_mode
        self.check_interval = check_interval
        
        # Components
        self.upbit = UpbitClient()
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        
        # 하이브리드 전략
        self.strategy = HybridStrategy(
            daily_target=1.0,
            ict_position_ratio=0.30,    # 최적화: 30% (공격적)
            trend_position_ratio=0.15   # 최적화: 15% (중간)
        )
        
        # 고정 거래 대상 (BTC 제외)
        self.target_symbols = [s.strip() for s in settings.ict_target_symbols.split(',')]
        
        # 포지션 관리
        self.positions: Dict[str, PositionInfo] = {}
        
        mode_str = "🔔 알림 전용" if self.mode == "semi" else "🤖 자동매매"
        logger.info(f"💹 AutoTrader 초기화 (하이브리드 전략) - {mode_str}")
        logger.info(f"   - 대상: {', '.join(self.target_symbols)}")
        logger.info(f"   - 일일 목표: {self.strategy.daily_target}%")
    
    async def start(self):
        """초기화"""
        await self.notifier.start()
        await self._sync_positions()
    
    async def stop(self):
        """종료"""
        await self.notifier.close()
    
    def _is_dust(self, balance: float, price: float) -> bool:
        """자투리 코인 여부"""
        return (balance * price) < 5000
    
    async def _sync_positions(self):
        """포지션 동기화"""
        try:
            balances = self.upbit.get_balances()
            if not balances:
                return
            
            self.positions.clear()
            
            for item in balances:
                currency = item.get('currency', '')
                if currency == 'KRW':
                    continue
                
                symbol = f"KRW-{currency}"
                
                if symbol not in self.target_symbols:
                    continue
                
                if symbol in settings.exclude_symbols:
                    continue
                
                balance = float(item.get('balance', 0) or 0)
                avg_buy_price = float(item.get('avg_buy_price', 0) or 0)
                current_price = self.upbit.get_current_price(symbol) or avg_buy_price
                
                if self._is_dust(balance, current_price):
                    continue
                
                self.positions[symbol] = PositionInfo(
                    in_position=True,
                    entry_price=avg_buy_price,
                    balance=balance,
                    strategy_type="UNKNOWN",  # 기존 포지션은 알 수 없음
                    entry_time=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"포지션 동기화 실패: {e}")
    
    def _get_position(self, symbol: str) -> PositionInfo:
        """포지션 조회"""
        if symbol not in self.positions:
            self.positions[symbol] = PositionInfo(
                in_position=False,
                entry_price=0.0,
                balance=0.0,
                strategy_type="NONE"
            )
        return self.positions[symbol]
    
    def analyze(self, symbol: str) -> Optional[HybridSignal]:
        """하이브리드 분석"""
        # 1시간봉 (ICT용)
        df_1h = self.upbit.get_ohlcv(symbol, interval="minute60", count=100)
        # 5분봉 (추세용)
        df_5m = self.upbit.get_ohlcv(symbol, interval="minute5", count=50)
        
        current_price = self.upbit.get_current_price(symbol)
        if current_price is None:
            return None
        
        position = self._get_position(symbol)
        
        signal = self.strategy.analyze(
            df_1h=df_1h,
            df_5m=df_5m,
            current_price=current_price,
            in_position=position.in_position,
            entry_price=position.entry_price,
            position_strategy=position.strategy_type
        )
        
        if signal.action != "HOLD":
            logger.info(f"🎯 {symbol} 신호: {signal}")
        else:
            logger.debug(f"⏸️ {symbol}: {signal.reason}")
        
        return signal
    
    async def execute_signal(
        self,
        symbol: str,
        signal: HybridSignal
    ) -> TradeResult:
        """신호 실행"""
        current_price = self.upbit.get_current_price(symbol)
        
        if current_price is None:
            return TradeResult(
                success=False, action=signal.action, symbol=symbol,
                order=None, signal=signal, price=None, amount=None,
                volume=None, strategy_type=signal.strategy_type, error="현재가 조회 실패"
            )
        
        # 포지션 크기 계산
        krw_balance = self.upbit.get_balance("KRW")
        amount = krw_balance * signal.position_size_ratio
        
        # 최소 금액 체크
        if amount < 5000:
            amount = 5000
        
        if signal.action == "HOLD":
            return TradeResult(
                success=True, action="HOLD", symbol=symbol,
                order=None, signal=signal, price=current_price,
                amount=None, volume=None, strategy_type=signal.strategy_type
            )
        
        # 리스크 체크
        can_trade, reason = self.risk_manager.can_trade(amount)
        if not can_trade and signal.action == "BUY":
            return TradeResult(
                success=False, action=signal.action, symbol=symbol,
                order=None, signal=signal, price=current_price,
                amount=amount, volume=None, strategy_type=signal.strategy_type, error=reason
            )
        
        # Semi 모드
        if self.mode == "semi":
            logger.info(f"🔔 Semi-auto [{signal.strategy_type}]: {symbol} {signal.action}")
            return TradeResult(
                success=True, action=f"SIGNAL_{signal.action}", symbol=symbol,
                order=None, signal=signal, price=current_price,
                amount=amount, volume=None, strategy_type=signal.strategy_type
            )
        
        # Full 모드
        if signal.action == "BUY":
            return await self._execute_buy(symbol, signal, amount, current_price)
        elif signal.action == "SELL":
            return await self._execute_sell(symbol, signal, current_price)
        
        return TradeResult(
            success=False, action=signal.action, symbol=symbol,
            order=None, signal=signal, price=current_price,
            amount=amount, volume=None, strategy_type=signal.strategy_type, error="Unknown action"
        )
    
    async def _execute_buy(self, symbol: str, signal: HybridSignal, amount: float, current_price: float) -> TradeResult:
        """매수 실행"""
        logger.info(f"🟢 [{signal.strategy_type}] 매수: {symbol}, ₩{amount:,.0f}")
        
        order = self.upbit.buy_market_order(symbol, amount)
        
        if order.success:
            volume = amount / current_price
            
            self.positions[symbol] = PositionInfo(
                in_position=True,
                entry_price=current_price,
                balance=volume,
                strategy_type=signal.strategy_type,
                entry_time=datetime.now()
            )
            
            await self.notifier.send_buy_alert(
                symbol=symbol, price=current_price, amount=amount,
                volume=volume, strategy=f"Hybrid_{signal.strategy_type}"
            )
            
            return TradeResult(
                success=True, action="BUY", symbol=symbol,
                order=order, signal=signal, price=current_price,
                amount=amount, volume=volume, strategy_type=signal.strategy_type
            )
        else:
            return TradeResult(
                success=False, action="BUY", symbol=symbol,
                order=order, signal=signal, price=current_price,
                amount=amount, volume=None, strategy_type=signal.strategy_type, error=order.error
            )
    
    async def _execute_sell(self, symbol: str, signal: HybridSignal, current_price: float) -> TradeResult:
        """매도 실행"""
        ticker = symbol.split('-')[1]
        balance = self.upbit.get_balance(ticker)
        
        if balance <= 0:
            self.positions[symbol] = PositionInfo(
                in_position=False, entry_price=0.0, balance=0.0, strategy_type="NONE"
            )
            return TradeResult(
                success=False, action="SELL", symbol=symbol,
                order=None, signal=signal, price=current_price,
                amount=None, volume=0, strategy_type=signal.strategy_type, error="매도 가능 수량 없음"
            )
        
        avg_buy_price = self.upbit.get_avg_buy_price(ticker)
        logger.info(f"🔴 [{signal.strategy_type}] 매도: {symbol}, {balance:.8f}")
        
        order = self.upbit.sell_market_order(symbol, balance)
        
        if order.success:
            total = balance * current_price
            profit = total - (balance * avg_buy_price) if avg_buy_price > 0 else 0
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
            
            # 전략에 수익률 업데이트
            self.strategy.update_profit(profit_rate)
            
            self.positions[symbol] = PositionInfo(
                in_position=False, entry_price=0.0, balance=0.0, strategy_type="NONE"
            )
            
            self.risk_manager.record_trade(amount=total, profit=profit, strategy=f"Hybrid_{signal.strategy_type}")
            
            await self.notifier.send_sell_alert(
                symbol=symbol, price=current_price, volume=balance, total=total,
                avg_buy_price=avg_buy_price, profit_rate=profit_rate,
                strategy=f"Hybrid_{signal.strategy_type}"
            )
            
            return TradeResult(
                success=True, action="SELL", symbol=symbol,
                order=order, signal=signal, price=current_price,
                amount=total, volume=balance, strategy_type=signal.strategy_type
            )
        else:
            return TradeResult(
                success=False, action="SELL", symbol=symbol,
                order=order, signal=signal, price=current_price,
                amount=None, volume=balance, strategy_type=signal.strategy_type, error=order.error
            )
    
    async def run_once(self) -> List[TradeResult]:
        """1회 분석 및 거래"""
        results = []
        
        await self._sync_positions()
        
        # 일일 목표 체크
        stats = self.strategy.get_daily_stats()
        if stats["target_achieved"]:
            logger.info(f"🎉 일일 목표 달성! ({stats['daily_profit']:.2f}%)")
        
        logger.info(f"📊 하이브리드 분석: {', '.join(self.target_symbols)} | 일일 수익: {stats['daily_profit']:.2f}%")
        
        for symbol in self.target_symbols:
            try:
                if symbol == "KRW-BTC":
                    continue
                
                if symbol in settings.exclude_symbols:
                    continue
                
                signal = self.analyze(symbol)
                if signal is None:
                    continue
                
                if signal.action != "HOLD":
                    result = await self.execute_signal(symbol, signal)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"❌ {symbol} 에러: {e}")
        
        return results


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("=== Hybrid AutoTrader Test ===\n")
        trader = AutoTrader(mode="semi")
        await trader.start()
        
        print(f"타겟: {trader.target_symbols}")
        print(f"일일 목표: {trader.strategy.daily_target}%\n")
        
        results = await trader.run_once()
        for r in results:
            print(f"  {r}")
        
        await trader.stop()
    
    asyncio.run(test())
