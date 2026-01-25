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
        top_n: int = 10  # 거래대금 상위 N개 종목
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
        
        # 멀티 심볼 포지션 상태 {symbol: PositionInfo}
        self.positions: Dict[str, PositionInfo] = {}
        
        mode_str = "🔔 알림 전용" if self.mode == "semi" else "🤖 자동매매"
        logger.info(f"💹 AutoTrader 초기화 완료 ({mode_str})")
        logger.info(f"   - 거래 대상: 거래대금 상위 {self.top_n}개 종목")
        logger.info(f"   - 1회 금액: ₩{settings.trade_amount:,.0f}")
        logger.info(f"   - 전략: 오더북 스캘핑 (비율: {settings.scalping_bid_ask_ratio}x, 익절: +{settings.scalping_take_profit}%, 손절: -{settings.scalping_stop_loss}%)")
    
    async def start(self):
        """Initialize components"""
        await self.notifier.start()
        
        # 기존 포지션 확인 (모든 KRW 보유 코인)
        self._check_existing_positions()
    
    async def stop(self):
        """Cleanup"""
        await self.notifier.close()
    
    def _check_existing_positions(self):
        """기존 포지션 확인 및 진입가 설정 (모든 KRW 보유 코인)"""
        try:
            balances = self.upbit.get_balances()
            if not balances:
                return
            
            for item in balances:
                currency = item.get('currency', '')
                if currency == 'KRW':
                    continue
                
                balance = float(item.get('balance', 0) or 0)
                avg_buy_price = float(item.get('avg_buy_price', 0) or 0)
                
                if balance > 0:
                    symbol = f"KRW-{currency}"
                    self.positions[symbol] = PositionInfo(
                        in_position=True,
                        entry_price=avg_buy_price,
                        balance=balance
                    )
                    logger.info(f"📊 기존 포지션 감지: {symbol} {balance:.8f} @ ₩{avg_buy_price:,.0f}")
                    
        except Exception as e:
            logger.error(f"기존 포지션 확인 실패: {e}")
    
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
        """
        특정 심볼의 시장 분석 (오더북 스캘핑)
        
        Args:
            symbol: 마켓 심볼 (예: "KRW-BTC")
        
        Returns:
            Signal 객체
        """
        # 오더북 데이터 조회
        orderbook = self.upbit.get_orderbook(symbol)
        if orderbook is None:
            logger.debug(f"오더북 데이터 조회 실패: {symbol}")
            return None
        
        current_price = self.upbit.get_current_price(symbol)
        if current_price is None:
            logger.debug(f"현재가 조회 실패: {symbol}")
            return None
        
        # 포지션 정보 조회
        position = self._get_position(symbol)
        
        # 오더북 스캘핑 전략 분석
        signal = self.strategy.analyze(
            orderbook=orderbook,
            current_price=current_price,
            entry_price=position.entry_price,
            in_position=position.in_position
        )
        
        # 의미 있는 신호만 로깅 (HOLD는 debug)
        if signal.action != "HOLD":
            logger.info(f"🎯 {symbol} 신호: {signal}")
        else:
            logger.debug(f"🎯 {symbol} 신호: HOLD")
        
        return signal
    
    async def execute_signal(
        self,
        symbol: str,
        signal: Signal,
        amount: float = None
    ) -> TradeResult:
        """
        신호에 따라 거래 실행
        
        Args:
            symbol: 마켓 심볼
            signal: 거래 신호
            amount: 거래 금액 (기본: settings.trade_amount)
            
        Returns:
            TradeResult
        """
        amount = amount or settings.trade_amount
        current_price = self.upbit.get_current_price(symbol)
        
        if current_price is None:
            return TradeResult(
                success=False,
                action=signal.action,
                symbol=symbol,
                order=None,
                signal=signal,
                price=None,
                amount=None,
                volume=None,
                error="현재가 조회 실패"
            )
        
        # HOLD 신호
        if signal.action == "HOLD":
            return TradeResult(
                success=True,
                action="HOLD",
                symbol=symbol,
                order=None,
                signal=signal,
                price=current_price,
                amount=None,
                volume=None
            )
        
        # 리스크 체크
        can_trade, reason = self.risk_manager.can_trade(amount)
        if not can_trade:
            logger.warning(f"⚠️ {symbol} 거래 불가: {reason}")
            return TradeResult(
                success=False,
                action=signal.action,
                symbol=symbol,
                order=None,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None,
                error=reason
            )
        
        # Semi-auto 모드: 알림 없이 신호만 로깅 (실거래 안함)
        if self.mode == "semi":
            logger.info(f"🔔 Semi-auto: {symbol} {signal.action} 신호 감지 (알림 없음)")
            
            return TradeResult(
                success=True,
                action=f"SIGNAL_{signal.action}",
                symbol=symbol,
                order=None,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None
            )
        
        # Full-auto 모드: 실제 거래
        if signal.action == "BUY":
            return await self._execute_buy(symbol, signal, amount, current_price)
        elif signal.action == "SELL":
            return await self._execute_sell(symbol, signal, current_price)
        
        return TradeResult(
            success=False,
            action=signal.action,
            symbol=symbol,
            order=None,
            signal=signal,
            price=current_price,
            amount=amount,
            volume=None,
            error=f"알 수 없는 액션: {signal.action}"
        )
    
    async def _execute_buy(
        self,
        symbol: str,
        signal: Signal,
        amount: float,
        current_price: float
    ) -> TradeResult:
        """매수 실행"""
        logger.info(f"🟢 매수 실행: {symbol}, ₩{amount:,.0f}")
        
        order = self.upbit.buy_market_order(symbol, amount)
        
        if order.success:
            # 체결 예상 수량
            volume = amount / current_price
            
            # 포지션 상태 업데이트
            self.positions[symbol] = PositionInfo(
                in_position=True,
                entry_price=current_price,
                balance=volume
            )
            
            # 리스크 매니저에 기록 (매수는 아직 손익 미확정)
            self.risk_manager.record_trade(
                amount=amount,
                profit=0,  # 매수 시점에는 손익 없음
                strategy=signal.strategy
            )
            
            # 알림 발송
            await self.notifier.send_buy_alert(
                symbol=symbol,
                price=current_price,
                amount=amount,
                volume=volume,
                strategy=signal.strategy
            )
            
            return TradeResult(
                success=True,
                action="BUY",
                symbol=symbol,
                order=order,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=volume
            )
        else:
            logger.error(f"❌ {symbol} 매수 실패: {order.error}")
            return TradeResult(
                success=False,
                action="BUY",
                symbol=symbol,
                order=order,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None,
                error=order.error
            )
    
    async def _execute_sell(
        self,
        symbol: str,
        signal: Signal,
        current_price: float
    ) -> TradeResult:
        """매도 실행 (전량 매도)"""
        ticker = symbol.split('-')[1]  # KRW-BTC -> BTC
        
        # 보유 수량 확인
        balance = self.upbit.get_balance(ticker)
        if balance <= 0:
            logger.warning(f"⚠️ 매도 가능 수량 없음: {symbol}")
            return TradeResult(
                success=False,
                action="SELL",
                symbol=symbol,
                order=None,
                signal=signal,
                price=current_price,
                amount=None,
                volume=0,
                error="매도 가능 수량 없음"
            )
        
        # 평균 매수가 조회
        avg_buy_price = self.upbit.get_avg_buy_price(ticker)
        
        logger.info(f"🔴 매도 실행: {symbol}, {balance:.8f} {ticker}")
        
        order = self.upbit.sell_market_order(symbol, balance)
        
        if order.success:
            total = balance * current_price
            
            # 수익률 계산
            profit_rate = None
            profit = 0
            if avg_buy_price > 0:
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                profit = total - (balance * avg_buy_price)
            
            # 포지션 상태 초기화
            self.positions[symbol] = PositionInfo(
                in_position=False,
                entry_price=0.0,
                balance=0.0
            )
            
            # 리스크 매니저에 기록
            self.risk_manager.record_trade(
                amount=total,
                profit=profit,
                strategy=signal.strategy
            )
            
            # 알림 발송
            await self.notifier.send_sell_alert(
                symbol=symbol,
                price=current_price,
                volume=balance,
                total=total,
                avg_buy_price=avg_buy_price,
                profit_rate=profit_rate,
                strategy=signal.strategy
            )
            
            return TradeResult(
                success=True,
                action="SELL",
                symbol=symbol,
                order=order,
                signal=signal,
                price=current_price,
                amount=total,
                volume=balance
            )
        else:
            logger.error(f"❌ {symbol} 매도 실패: {order.error}")
            return TradeResult(
                success=False,
                action="SELL",
                symbol=symbol,
                order=order,
                signal=signal,
                price=current_price,
                amount=None,
                volume=balance,
                error=order.error
            )
    
    async def run_once(self) -> List[TradeResult]:
        """
        1회 분석 및 거래 실행 (상위 N개 종목 + 기존 포지션)
        
        Returns:
            List[TradeResult] - 각 심볼별 거래 결과
        """
        results = []
        
        # 1. 거래대금 상위 N개 종목 조회
        top_symbols = self.upbit.get_top_volume_tickers(self.top_n)
        if not top_symbols:
            logger.warning("거래대금 상위 종목 조회 실패")
            return results
        
        # 2. 기존 포지션 중 상위 N개에 없는 심볼도 체크 (익절/손절용)
        symbols_to_check = set(top_symbols)
        for symbol, position in self.positions.items():
            if position.in_position:
                symbols_to_check.add(symbol)
        
        logger.info(f"📡 {len(symbols_to_check)}개 종목 분석 중...")
        
        # 3. 각 심볼별 분석 및 거래
        for symbol in symbols_to_check:
            try:
                # 제외 목록에 있는 심볼은 건드리지 않음
                if symbol in settings.exclude_symbols:
                    logger.debug(f"⏭️ {symbol} 건너뜀 (제외 목록)")
                    continue
                
                signal = self.analyze(symbol)
                if signal is None:
                    continue
                
                # HOLD가 아닌 신호만 실행
                if signal.action != "HOLD":
                    result = await self.execute_signal(symbol, signal)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"❌ {symbol} 처리 중 에러: {e}")
        
        return results


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test_trader():
        print("=== AutoTrader Test (Multi-Symbol Orderbook Scalping) ===\n")
        
        trader = AutoTrader(mode="semi", top_n=5)
        await trader.start()
        
        # 상위 5개 종목 분석
        results = await trader.run_once()
        print(f"\n거래 결과: {len(results)}건")
        for r in results:
            print(f"  - {r}")
        
        await trader.stop()
    
    asyncio.run(test_trader())
