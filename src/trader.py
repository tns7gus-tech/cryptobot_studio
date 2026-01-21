"""
CryptoBot Studio - Auto Trading Engine
Executes trades based on strategy signals
"""
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from config import settings
from upbit_client import UpbitClient, OrderResult
from indicators import detect_fvg, FVGResult
from strategies import FVGStrategy, Signal
from telegram_notifier import TelegramNotifier
from risk_manager import RiskManager


@dataclass
class TradeResult:
    """거래 결과"""
    success: bool
    action: str  # "BUY", "SELL", "SKIP"
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
            return f"✅ {self.action}: {price_str} x {volume_str}"
        return f"❌ {self.action}: {self.error}"


class AutoTrader:
    """
    자동매매 엔진
    
    Modes:
    - semi: 신호만 알림 (실거래 안함)
    - full: 자동 매매
    """
    
    def __init__(
        self,
        mode: Literal["semi", "full"] = None,
        symbol: str = None
    ):
        self.mode = mode or settings.bot_mode
        self.symbol = symbol or settings.trade_symbol
        
        # Components
        self.upbit = UpbitClient()
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        
        # ICT FVG 전략 (30분봉)
        self.fvg_strategy = FVGStrategy(min_gap_percent=0.05)
        self.active_strategy = self.fvg_strategy
        
        # 활성 FVG 상태 추적
        self._active_fvg = None
        self._in_position = False  # 포지션 보유 여부
        
        mode_str = "🔔 알림 전용" if self.mode == "semi" else "🤖 자동매매"
        logger.info(f"💹 AutoTrader 초기화 완료 ({mode_str})")
        logger.info(f"   - 마켓: {self.symbol}")
        logger.info(f"   - 1회 금액: ₩{settings.trade_amount:,.0f}")
        logger.info(f"   - 전략: ICT Fair Value Gap (30분봉)")
    
    async def start(self):
        """Initialize components"""
        await self.notifier.start()
    
    async def stop(self):
        """Cleanup"""
        await self.notifier.close()
    
    def analyze(self) -> Optional[Signal]:
        """
        현재 시장 분석 (30분봉 ICT FVG 전략)
        
        Returns:
            Signal 객체
        """
        # OHLCV 데이터 조회 (30분봉)
        df = self.upbit.get_ohlcv(self.symbol, interval="minute30", count=100)
        if df is None:
            logger.error("OHLCV 데이터 조회 실패")
            return None
        
        current_price = self.upbit.get_current_price(self.symbol)
        if current_price is None:
            logger.error("현재가 조회 실패")
            return None
        
        # FVG 탐지 (30분봉)
        fvg = detect_fvg(df, min_gap_percent=0.05)
        
        if fvg and fvg.found:
            logger.info(f"📊 {fvg}")
            self._active_fvg = fvg
        else:
            logger.debug("FVG 미발견")
        
        # ICT FVG 전략 분석
        signal = self.fvg_strategy.analyze(
            ohlcv_df=df,
            current_price=current_price,
            fvg_result=fvg
        )
        
        logger.info(f"🎯 신호: {signal}")
        return signal
    
    async def execute_signal(
        self,
        signal: Signal,
        amount: float = None
    ) -> TradeResult:
        """
        신호에 따라 거래 실행
        
        Args:
            signal: 거래 신호
            amount: 거래 금액 (기본: settings.trade_amount)
            
        Returns:
            TradeResult
        """
        amount = amount or settings.trade_amount
        current_price = self.upbit.get_current_price(self.symbol)
        
        if current_price is None:
            return TradeResult(
                success=False,
                action=signal.action,
                order=None,
                signal=signal,
                price=None,
                amount=None,
                volume=None,
                error="현재가 조회 실패"
            )
        
        # HOLD 신호
        if signal.action == "HOLD":
            logger.debug("⏸️ HOLD 신호 - 거래 없음")
            return TradeResult(
                success=True,
                action="HOLD",
                order=None,
                signal=signal,
                price=current_price,
                amount=None,
                volume=None
            )
        
        # 리스크 체크
        can_trade, reason = self.risk_manager.can_trade(amount)
        if not can_trade:
            logger.warning(f"⚠️ 거래 불가: {reason}")
            return TradeResult(
                success=False,
                action=signal.action,
                order=None,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None,
                error=reason
            )
        
        # Semi-auto 모드: 알림 없이 신호만 로깅 (실거래 안함)
        if self.mode == "semi":
            logger.info(f"🔔 Semi-auto: {signal.action} 신호 감지 (알림 없음)")
            
            return TradeResult(
                success=True,
                action=f"SIGNAL_{signal.action}",
                order=None,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None
            )
        
        # Full-auto 모드: 실제 거래
        if signal.action == "BUY":
            return await self._execute_buy(signal, amount, current_price)
        elif signal.action == "SELL":
            return await self._execute_sell(signal, current_price)
        
        return TradeResult(
            success=False,
            action=signal.action,
            order=None,
            signal=signal,
            price=current_price,
            amount=amount,
            volume=None,
            error=f"알 수 없는 액션: {signal.action}"
        )
    
    async def _execute_buy(
        self,
        signal: Signal,
        amount: float,
        current_price: float
    ) -> TradeResult:
        """매수 실행"""
        logger.info(f"🟢 매수 실행: {self.symbol}, ₩{amount:,.0f}")
        
        order = self.upbit.buy_market_order(self.symbol, amount)
        
        if order.success:
            # 체결 예상 수량
            volume = amount / current_price
            
            # 리스크 매니저에 기록 (매수는 아직 손익 미확정)
            self.risk_manager.record_trade(
                amount=amount,
                profit=0,  # 매수 시점에는 손익 없음
                strategy=signal.strategy
            )
            
            # 알림 발송
            await self.notifier.send_buy_alert(
                symbol=self.symbol,
                price=current_price,
                amount=amount,
                volume=volume,
                strategy=signal.strategy
            )
            
            return TradeResult(
                success=True,
                action="BUY",
                order=order,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=volume
            )
        else:
            logger.error(f"❌ 매수 실패: {order.error}")
            return TradeResult(
                success=False,
                action="BUY",
                order=order,
                signal=signal,
                price=current_price,
                amount=amount,
                volume=None,
                error=order.error
            )
    
    async def _execute_sell(
        self,
        signal: Signal,
        current_price: float
    ) -> TradeResult:
        """매도 실행 (전량 매도)"""
        ticker = self.symbol.split('-')[1]  # KRW-BTC -> BTC
        
        # 보유 수량 확인
        balance = self.upbit.get_balance(ticker)
        if balance <= 0:
            logger.warning(f"⚠️ 매도 가능 수량 없음: {ticker}")
            return TradeResult(
                success=False,
                action="SELL",
                order=None,
                signal=signal,
                price=current_price,
                amount=None,
                volume=0,
                error="매도 가능 수량 없음"
            )
        
        # 평균 매수가 조회
        avg_buy_price = self.upbit.get_avg_buy_price(ticker)
        
        logger.info(f"🔴 매도 실행: {self.symbol}, {balance:.8f} {ticker}")
        
        order = self.upbit.sell_market_order(self.symbol, balance)
        
        if order.success:
            total = balance * current_price
            
            # 수익률 계산
            profit_rate = None
            profit = 0
            if avg_buy_price > 0:
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                profit = total - (balance * avg_buy_price)
            
            # 리스크 매니저에 기록
            self.risk_manager.record_trade(
                amount=total,
                profit=profit,
                strategy=signal.strategy
            )
            
            # 알림 발송
            await self.notifier.send_sell_alert(
                symbol=self.symbol,
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
                order=order,
                signal=signal,
                price=current_price,
                amount=total,
                volume=balance
            )
        else:
            logger.error(f"❌ 매도 실패: {order.error}")
            return TradeResult(
                success=False,
                action="SELL",
                order=order,
                signal=signal,
                price=current_price,
                amount=None,
                volume=balance,
                error=order.error
            )
    
    async def run_once(self) -> TradeResult:
        """
        1회 분석 및 거래 실행
        
        Returns:
            TradeResult
        """
        signal = self.analyze()
        if signal is None:
            return TradeResult(
                success=False,
                action="ANALYZE",
                order=None,
                signal=None,
                price=None,
                amount=None,
                volume=None,
                error="분석 실패"
            )
        
        return await self.execute_signal(signal)


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test_trader():
        print("=== AutoTrader Test ===\n")
        
        trader = AutoTrader(mode="semi")
        await trader.start()
        
        # 분석만 실행
        signal = trader.analyze()
        if signal:
            print(f"\n신호: {signal}")
        
        await trader.stop()
    
    asyncio.run(test_trader())
