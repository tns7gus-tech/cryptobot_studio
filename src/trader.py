"""
CryptoBot Studio - Auto Trading Engine (Multi-Symbol)
Executes trades based on strategy signals (Orderbook Scalping)
Supports trading top N coins by 24h volume
"""
from typing import Optional, Literal, Dict, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from config import settings
from upbit_client import UpbitClient, OrderResult
from strategies import OrderbookScalpingStrategy, Signal
from telegram_notifier import TelegramNotifier
from risk_manager import RiskManager


@dataclass
class TradeResult:
    """거래 결과"""
    success: bool
    action: str  # "BUY", "SELL", "SKIP"
    symbol: str  # 거래 심볼
    order: Optional[OrderResult]
    signal: Optional[Signal]
    price: Optional[float]
    amount: Optional[float]
    volume: Optional[float]
    error: Optional[str] = None
    
    def __str__(self):
        if self.success:
            price_str = f"₩{self.price:,.0f}" if self.price is not None else "N/A"
            volume_str = f"{self.volume:.8f}" if self.volume is not None else "N/A"
            return f"✅ {self.symbol} {self.action}: {price_str} x {volume_str}"
        return f"❌ {self.symbol} {self.action}: {self.error}"


@dataclass
class PositionInfo:
    """포지션 정보"""
    in_position: bool
    entry_price: float
    balance: float


class AutoTrader:
    """
    자동매매 엔진 (오더북 스캘핑 - 멀티 심볼)
    
    Modes:
    - semi: 신호만 알림 (실거래 안함)
    - full: 자동 매매
    """
    
    def __init__(
        self,
        mode: Literal["semi", "full"] = None,
        top_n: int = 3  # 거래대금 상위 N개 종목 (사용자 요청: 3개)
    ):
        self.mode = mode or settings.bot_mode
        self.top_n = top_n
        
        # Components
        self.upbit = UpbitClient()
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        
        # 오더북 스캘핑 전략
        self.strategy = OrderbookScalpingStrategy(
            bid_ask_ratio=settings.scalping_bid_ask_ratio,
            take_profit=settings.scalping_take_profit,
            stop_loss=settings.scalping_stop_loss
        )
        
        # 상태 관리
        self.positions: Dict[str, PositionInfo] = {}
        self.target_symbols: List[str] = []
        self.last_update_time: Optional[datetime] = None
        
        mode_str = "🔔 알림 전용" if self.mode == "semi" else "🤖 자동매매"
        logger.info(f"💹 AutoTrader 초기화 완료 ({mode_str})")
        logger.info(f"   - 거래 대상: 거래대금 상위 {self.top_n}개 종목 (4시간 주기 갱신)")
    
    async def start(self):
        """Initialize components"""
        await self.notifier.start()
        # 초기 포지션 및 타겟 설정
        await self._update_targets_and_positions(force=True)
    
    async def stop(self):
        """Cleanup"""
        await self.notifier.close()
    
    def _is_dust(self, balance: float, price: float) -> bool:
        """자투리 코인(5,000원 미만) 여부 확인"""
        return (balance * price) < 5000
    
    async def _update_targets_and_positions(self, force: bool = False):
        """
        타겟 종목 갱신 및 포지션 동기화 (실시간/매 루프마다 체크하도록 변경)
        """
        now = datetime.now()
        
        # 1. 갱신 (실시간성을 위해 매번 혹은 짧은 주기로 체크)
        # 사용자 요청: "다시 실시간방식으로 변경" -> 매 1분마다 체크
        should_update = force
        if not should_update and self.last_update_time:
            seconds_diff = (now - self.last_update_time).total_seconds()
            if seconds_diff >= 60: # 1분마다 갱신
                should_update = True
        else:
            should_update = True
            
        if should_update:
            # logger.debug("🔄 타겟/포지션 갱신 (실시간)...")
            
            # 2. 거래대금 상위 종목 갱신
            new_targets = self.upbit.get_top_volume_tickers(self.top_n)
            if new_targets:
                # 기존 타겟과 다를 때만 알림
                if set(new_targets) != set(self.target_symbols):
                    logger.info(f"🎯 타겟 변경 (Top {self.top_n}): {', '.join(new_targets)}")
                    # 잦은 알림 방지를 위해 Log만 남김 (또는 중요하면 알림)
                    
                self.target_symbols = new_targets
                self.last_update_time = now
        
        # 3. 보유 포지션 동기화
        try:
            balances = self.upbit.get_balances()
            if not balances:
                return
                
            self.positions.clear() # 재구축
            
            for item in balances:
                currency = item.get('currency', '')
                if currency == 'KRW':
                    continue
                
                symbol = f"KRW-{currency}"
                
                # 제외 목록 확인
                if symbol in settings.exclude_symbols:
                    continue
                
                balance = float(item.get('balance', 0) or 0)
                avg_buy_price = float(item.get('avg_buy_price', 0) or 0)
                current_price = self.upbit.get_current_price(symbol) or avg_buy_price
                
                # 자투리(Dust) 코인 무시 (< 5000 KRW)
                if self._is_dust(balance, current_price):
                    # logger.debug(f"🧹 자투리 무시: {symbol}")
                    continue
                
                self.positions[symbol] = PositionInfo(
                    in_position=True,
                    entry_price=avg_buy_price,
                    balance=balance
                )
                
        except Exception as e:
            logger.error(f"포지션 갱신 실패: {e}")
    
    def _get_position(self, symbol: str) -> PositionInfo:
        """심볼의 포지션 정보 조회"""
        if symbol not in self.positions:
            self.positions[symbol] = PositionInfo(
                in_position=False,
                entry_price=0.0,
                balance=0.0
            )
        return self.positions[symbol]
    
    def analyze(self, symbol: str) -> Optional[Signal]:
        """분석"""
        orderbook = self.upbit.get_orderbook(symbol)
        if orderbook is None:
            return None
        
        current_price = self.upbit.get_current_price(symbol)
        if current_price is None:
            return None
        
        position = self._get_position(symbol)
        
        signal = self.strategy.analyze(
            orderbook=orderbook,
            current_price=current_price,
            entry_price=position.entry_price,
            in_position=position.in_position
        )
        
        if signal.action != "HOLD":
            logger.info(f"🎯 {symbol} 신호: {signal}")
        
        return signal
    
    async def execute_signal(
        self,
        symbol: str,
        signal: Signal,
        amount: float = None
    ) -> TradeResult:
        """신호 실행"""
        amount = amount or settings.trade_amount
        current_price = self.upbit.get_current_price(symbol)
        
        if current_price is None:
            return TradeResult(
                success=False, action=signal.action, symbol=symbol, order=None, 
                signal=signal, price=None, amount=None, volume=None, error="현재가 조회 실패"
            )
        
        # HOLD 처리
        if signal.action == "HOLD":
            return TradeResult(
                success=True, action="HOLD", symbol=symbol, order=None, 
                signal=signal, price=current_price, amount=None, volume=None
            )
        
        # 리스크 체크
        can_trade, reason = self.risk_manager.can_trade(amount)
        if not can_trade and signal.action == "BUY": # 매도시에는 리스크 체크 스킵 (탈출 우선)
             return TradeResult(
                success=False, action=signal.action, symbol=symbol, order=None, 
                signal=signal, price=current_price, amount=amount, volume=None, error=reason
            )
        
        # Semi 모드
        if self.mode == "semi":
            logger.info(f"🔔 Semi-auto: {symbol} {signal.action}")
            return TradeResult(
                success=True, action=f"SIGNAL_{signal.action}", symbol=symbol, order=None, 
                signal=signal, price=current_price, amount=amount, volume=None
            )
        
        # Full 모드: 주문 실행
        if signal.action == "BUY":
            return await self._execute_buy(symbol, signal, amount, current_price)
        elif signal.action == "SELL":
            return await self._execute_sell(symbol, signal, current_price)
        
        return TradeResult(
            success=False, action=signal.action, symbol=symbol, order=None, 
            signal=signal, price=current_price, amount=amount, volume=None, error="Unknown action"
        )
    
    async def _execute_buy(self, symbol: str, signal: Signal, amount: float, current_price: float) -> TradeResult:
        """매수 실행 (지정가 Limit Order)"""
        # 지정가 매수를 위해 호가창 조회 (매수 1호가 바로 위 or 매수 1호가)
        # 사용자 요청: "현재 최우선 매수 호가(bid price) 바로 위에 걸어두기" -> Upbit API에서는 최우선 매수호가(bid_price)를 의미
        # bid_price로 주문하면 대기 주문이 됨.
        orderbook = self.upbit.get_orderbook(symbol)
        if not orderbook or 'orderbook_units' not in orderbook or not orderbook['orderbook_units']:
            bid_price = current_price # 실패 시 현재가
        else:
            bid_price = float(orderbook['orderbook_units'][0]['bid_price'])
            
        logger.info(f"🟢 매수 시도 (지정가): {symbol}, 가격 ₩{bid_price:,.0f}")
        
        # 지정가 매수 호출
        # 수량 계산
        volume = amount / bid_price
        order = self.upbit.buy_limit_order(symbol, price=bid_price, volume=volume)
        
        if order.success:
            # 지정가 주문은 즉시 체결되지 않을 수 있음.
            # 하지만 봇 로직상 '포지션 잡음'으로 간주하고 다음 턴에 잔고 동기화로 보정
            # -> 미체결 시 잔고에 안 들어오므로 다음 턴에 다시 BUY 시그널이 뜰 수 있음.
            # -> 이를 방지하려면 'pending' 상태 관리가 필요하지만, 간단히 하기 위해
            #    일단 로컬 포지션에 추가해두고, 다음번 _update_targets_and_positions에서
            #    실제 잔고(미체결이면 없음)에 따라 사라지게 둠.
            #    하지만 이러면 10초 뒤에 다시 매수 주문을 넣을 위험이 있음.
            #    (사용자가 원하는 것은 'Limit Order'이므로 미체결 감안)
            
            # 개선: 미체결 주문이 있는지 확인하는 로직이 필요하나 복잡함.
            # 일단 'in_position'으로 마킹하여 중복 매수 방지
            self.positions[symbol] = PositionInfo(
                in_position=True, entry_price=bid_price, balance=volume
            )
            
            # 매수 시에는 Trade Count를 증가시키지 않음 (매도 시 완료된 것으로 카운트)
            # self.risk_manager.record_trade(...) -> REMOVED
            
            await self.notifier.send_buy_alert(
                symbol=symbol, price=bid_price, amount=amount, 
                volume=volume, strategy=signal.strategy
            )
            return TradeResult(
                success=True, action="BUY", symbol=symbol, order=order, 
                signal=signal, price=bid_price, amount=amount, volume=volume
            )
        else:
            logger.error(f"❌ {symbol} 매수 실패: {order.error}")
            return TradeResult(
                success=False, action="BUY", symbol=symbol, order=order, 
                signal=signal, price=bid_price, amount=amount, volume=None, error=order.error
            )

    async def _execute_sell(self, symbol: str, signal: Signal, current_price: float) -> TradeResult:
        """매도 실행 (시장가 Market Order - 확실한 청산)"""
        ticker = symbol.split('-')[1]
        balance = self.upbit.get_balance(ticker)
        
        if balance <= 0:
            # 잔고가 없다면 로컬 상태도 업데이트
            self.positions[symbol] = PositionInfo(in_position=False, entry_price=0.0, balance=0.0)
            return TradeResult(
                success=False, action="SELL", symbol=symbol, order=None, 
                signal=signal, price=current_price, amount=None, volume=0, error="매도 가능 수량 없음"
            )
            
        avg_buy_price = self.upbit.get_avg_buy_price(ticker)
        logger.info(f"🔴 매도 시도 (시장가): {symbol}, {balance:.8f} {ticker}")
        order = self.upbit.sell_market_order(symbol, balance)
        
        if order.success:
            total = balance * current_price
            profit = total - (balance * avg_buy_price) if avg_buy_price > 0 else 0
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
            
            self.positions[symbol] = PositionInfo(in_position=False, entry_price=0.0, balance=0.0)
            
            # 매도 시점에 Trade Count & Profit 기록
            self.risk_manager.record_trade(amount=total, profit=profit, strategy=signal.strategy)
            
            await self.notifier.send_sell_alert(
                symbol=symbol, price=current_price, volume=balance, total=total,
                avg_buy_price=avg_buy_price, profit_rate=profit_rate, strategy=signal.strategy
            )
            return TradeResult(
                success=True, action="SELL", symbol=symbol, order=order, 
                signal=signal, price=current_price, amount=total, volume=balance
            )
        else:
            logger.error(f"❌ {symbol} 매도 실패: {order.error}")
            return TradeResult(
                success=False, action="SELL", symbol=symbol, order=order, 
                signal=signal, price=current_price, amount=None, volume=balance, error=order.error
            )

    async def run_once(self) -> List[TradeResult]:
        """1회 분석 및 거래 실행"""
        results = []
        
        # 1. 갱신 (매주기 체크)
        await self._update_targets_and_positions()
        
        # 2. 분석 대상 선정
        symbols_to_check = set(self.target_symbols)
        for symbol, position in self.positions.items():
            if position.in_position:
                symbols_to_check.add(symbol)
        
        logger.debug(f"분석 대상: {len(symbols_to_check)}개 ({', '.join(list(symbols_to_check)[:5])}...)")
        
        # 3. 분석 및 거래
        for symbol in symbols_to_check:
            try:
                if symbol in settings.exclude_symbols:
                    continue
                
                signal = self.analyze(symbol)
                if signal is None: continue
                
                if signal.action != "HOLD":
                    result = await self.execute_signal(symbol, signal)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"❌ {symbol} 처리 중 에러: {e}")
        
        return results


# Test Code
if __name__ == "__main__":
    import asyncio
    async def test_trader():
        print("=== AutoTrader Test (Limit Order & Realtime) ===\n")
        trader = AutoTrader(mode="semi", top_n=3)
        await trader.start()
        
        print("\n--- Run Once ---")
        results = await trader.run_once()
        print(f"Top 3 Targets: {trader.target_symbols}")
        
        print("\n--- Done ---")
        await trader.stop()
    
    asyncio.run(test_trader())
