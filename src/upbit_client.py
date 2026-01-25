"""
CryptoBot Studio - Upbit Exchange Client
Handles all interactions with Upbit API
"""
import pyupbit
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from config import settings


@dataclass
class OrderResult:
    """주문 결과"""
    success: bool
    uuid: Optional[str]
    side: str  # bid (매수) or ask (매도)
    ord_type: str
    price: Optional[float]
    volume: Optional[float]
    executed_volume: Optional[float]
    avg_price: Optional[float]
    total: Optional[float]  # 총 거래 금액
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'uuid': self.uuid,
            'side': self.side,
            'ord_type': self.ord_type,
            'price': self.price,
            'volume': self.volume,
            'executed_volume': self.executed_volume,
            'avg_price': self.avg_price,
            'total': self.total,
            'error': self.error
        }


class UpbitClient:
    """
    Upbit 거래소 API 클라이언트
    
    기능:
    - 시세 조회
    - 잔고 조회
    - 시장가 매수/매도
    - OHLCV 캔들 데이터 조회
    """
    
    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None
    ):
        self.access_key = access_key or settings.upbit_access_key
        self.secret_key = secret_key or settings.upbit_secret_key
        
        # Initialize authenticated client
        try:
            self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)
            logger.info("🔑 Upbit 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"❌ Upbit 클라이언트 초기화 실패: {e}")
            self.upbit = None
    
    def is_connected(self) -> bool:
        """API 연결 상태 확인"""
        if not self.upbit:
            return False
        try:
            balance = self.upbit.get_balance("KRW")
            return balance is not None
        except:
            return False
    
    def get_balance(self, ticker: str = "KRW") -> float:
        """
        잔고 조회
        
        Args:
            ticker: 조회할 통화 (예: "KRW", "BTC", "ETH")
            
        Returns:
            잔고 (없으면 0.0)
        """
        if not self.upbit:
            logger.error("Upbit 클라이언트가 초기화되지 않음")
            return 0.0
        
        try:
            balance = self.upbit.get_balance(ticker)
            return float(balance) if balance else 0.0
        except Exception as e:
            logger.error(f"잔고 조회 실패 ({ticker}): {e}")
            return 0.0
    
    def get_balances(self) -> List[Dict]:
        """
        전체 잔고 조회
        
        Returns:
            잔고 목록
        """
        if not self.upbit:
            return []
        
        try:
            return self.upbit.get_balances()
        except Exception as e:
            logger.error(f"전체 잔고 조회 실패: {e}")
            return []
    
    def get_top_volume_tickers(self, limit: int = 10) -> List[str]:
        """
        24시간 거래대금 상위 종목 조회 (KRW 마켓만)
        
        Args:
            limit: 상위 몇 개를 가져올지 (기본 10개)
            
        Returns:
            거래대금 상위 종목 리스트 (예: ["KRW-BTC", "KRW-XRP", ...])
        """
        try:
            # KRW 마켓 전체 티커 조회
            tickers = pyupbit.get_tickers(fiat="KRW")
            if not tickers:
                logger.error("KRW 마켓 티커 조회 실패")
                return []
            
            # 각 티커의 24시간 거래대금 조회
            ticker_data = pyupbit.get_current_price(tickers, verbose=True)
            
            if not ticker_data:
                logger.error("티커 정보 조회 실패")
                return []
            
            # 리스트로 변환 (단일 티커인 경우 대비)
            if isinstance(ticker_data, dict):
                ticker_data = [ticker_data]
            
            # 거래대금 기준 정렬 (acc_trade_price_24h)
            sorted_tickers = sorted(
                ticker_data,
                key=lambda x: float(x.get('acc_trade_price_24h', 0) or 0),
                reverse=True
            )
            
            # 상위 N개 심볼 추출
            top_symbols = [t['market'] for t in sorted_tickers[:limit]]
            
            logger.info(f"📊 거래대금 상위 {limit}개: {', '.join(top_symbols)}")
            return top_symbols
            
        except Exception as e:
            logger.error(f"거래대금 상위 종목 조회 실패: {e}")
            return []

    
    def get_current_price(self, symbol: str = None) -> Optional[float]:
        """
        현재가 조회
        
        Args:
            symbol: 마켓 심볼 (예: "KRW-BTC")
            
        Returns:
            현재가 (실패 시 None)
        """
        symbol = symbol or settings.trade_symbol
        
        try:
            price = pyupbit.get_current_price(symbol)
            return float(price) if price else None
        except Exception as e:
            logger.error(f"현재가 조회 실패 ({symbol}): {e}")
            return None
    
    def get_ticker(self, symbol: str = None) -> Optional[Dict]:
        """
        티커 정보 조회 (현재가, 거래량 등)
        
        Args:
            symbol: 마켓 심볼
            
        Returns:
            티커 정보 딕셔너리
        """
        symbol = symbol or settings.trade_symbol
        
        try:
            ticker = pyupbit.get_current_price(symbol, verbose=True)
            if ticker and len(ticker) > 0:
                return ticker[0] if isinstance(ticker, list) else ticker
            return None
        except Exception as e:
            logger.error(f"티커 조회 실패 ({symbol}): {e}")
            return None
    
    def get_ohlcv(
        self,
        symbol: str = None,
        interval: str = "minute60",
        count: int = 200
    ) -> Optional[Any]:
        """
        OHLCV 캔들 데이터 조회
        
        Args:
            symbol: 마켓 심볼
            interval: 시간 간격 
                - "minute1", "minute3", "minute5", "minute10", "minute15", 
                - "minute30", "minute60", "minute240"
                - "day", "week", "month"
            count: 조회할 캔들 개수 (최대 200)
            
        Returns:
            pandas DataFrame (open, high, low, close, volume)
        """
        symbol = symbol or settings.trade_symbol
        
        try:
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
            if df is not None and len(df) > 0:
                logger.debug(f"OHLCV 조회 성공: {symbol} ({len(df)}개)")
                return df
            return None
        except Exception as e:
            logger.error(f"OHLCV 조회 실패 ({symbol}): {e}")
            return None
    
    def buy_market_order(
        self,
        symbol: str = None,
        price: float = None
    ) -> OrderResult:
        """
        시장가 매수
        
        Args:
            symbol: 마켓 심볼
            price: 매수 금액 (KRW)
            
        Returns:
            OrderResult
        """
        symbol = symbol or settings.trade_symbol
        price = price or settings.trade_amount
        
        if not self.upbit:
            return OrderResult(
                success=False,
                uuid=None,
                side="bid",
                ord_type="price",
                price=price,
                volume=None,
                executed_volume=None,
                avg_price=None,
                total=None,
                error="Upbit 클라이언트 미초기화"
            )
        
        try:
            logger.info(f"🟢 시장가 매수 요청: {symbol}, ₩{price:,.0f}")
            
            result = self.upbit.buy_market_order(symbol, price)
            
            if result and 'uuid' in result:
                logger.success(f"✅ 매수 주문 성공: {result['uuid']}")
                
                return OrderResult(
                    success=True,
                    uuid=result.get('uuid'),
                    side=result.get('side', 'bid'),
                    ord_type=result.get('ord_type', 'price'),
                    price=float(result.get('price', price)),
                    volume=float(result.get('volume', 0)) if result.get('volume') else None,
                    executed_volume=float(result.get('executed_volume', 0)) if result.get('executed_volume') else None,
                    avg_price=None,  # 체결 후 조회 필요
                    total=price
                )
            else:
                error_msg = result.get('error', {}).get('message', str(result)) if result else "Unknown error"
                logger.error(f"❌ 매수 주문 실패: {error_msg}")
                
                return OrderResult(
                    success=False,
                    uuid=None,
                    side="bid",
                    ord_type="price",
                    price=price,
                    volume=None,
                    executed_volume=None,
                    avg_price=None,
                    total=None,
                    error=error_msg
                )
                
        except Exception as e:
            logger.error(f"❌ 매수 주문 예외: {e}")
            return OrderResult(
                success=False,
                uuid=None,
                side="bid",
                ord_type="price",
                price=price,
                volume=None,
                executed_volume=None,
                avg_price=None,
                total=None,
                error=str(e)
            )
    
    def sell_market_order(
        self,
        symbol: str = None,
        volume: float = None
    ) -> OrderResult:
        """
        시장가 매도
        
        Args:
            symbol: 마켓 심볼
            volume: 매도 수량
            
        Returns:
            OrderResult
        """
        symbol = symbol or settings.trade_symbol
        
        if not self.upbit:
            return OrderResult(
                success=False,
                uuid=None,
                side="ask",
                ord_type="market",
                price=None,
                volume=volume,
                executed_volume=None,
                avg_price=None,
                total=None,
                error="Upbit 클라이언트 미초기화"
            )
        
        # volume이 없으면 전체 보유량 매도
        if volume is None:
            ticker = symbol.split('-')[1]  # KRW-BTC -> BTC
            volume = self.get_balance(ticker)
            
            if volume <= 0:
                return OrderResult(
                    success=False,
                    uuid=None,
                    side="ask",
                    ord_type="market",
                    price=None,
                    volume=0,
                    executed_volume=None,
                    avg_price=None,
                    total=None,
                    error="매도 가능 수량 없음"
                )
        
        try:
            logger.info(f"🔴 시장가 매도 요청: {symbol}, {volume}")
            
            result = self.upbit.sell_market_order(symbol, volume)
            
            if result and 'uuid' in result:
                logger.success(f"✅ 매도 주문 성공: {result['uuid']}")
                
                return OrderResult(
                    success=True,
                    uuid=result.get('uuid'),
                    side=result.get('side', 'ask'),
                    ord_type=result.get('ord_type', 'market'),
                    price=None,
                    volume=float(result.get('volume', volume)),
                    executed_volume=float(result.get('executed_volume', 0)) if result.get('executed_volume') else None,
                    avg_price=None,
                    total=None
                )
            else:
                error_msg = result.get('error', {}).get('message', str(result)) if result else "Unknown error"
                logger.error(f"❌ 매도 주문 실패: {error_msg}")
                
                return OrderResult(
                    success=False,
                    uuid=None,
                    side="ask",
                    ord_type="market",
                    price=None,
                    volume=volume,
                    executed_volume=None,
                    avg_price=None,
                    total=None,
                    error=error_msg
                )
                
        except Exception as e:
            logger.error(f"❌ 매도 주문 예외: {e}")
            return OrderResult(
                success=False,
                uuid=None,
                side="ask",
                ord_type="market",
                price=None,
                volume=volume,
                executed_volume=None,
                avg_price=None,
                total=None,
                error=str(e)
            )
    
    def get_orderbook(self, symbol: str = None) -> Optional[Dict]:
        """
        호가창(오더북) 조회
        
        Args:
            symbol: 마켓 심볼 (예: "KRW-BTC")
            
        Returns:
            {
                'total_ask_size': 총 매도 잔량,
                'total_bid_size': 총 매수 잔량,
                'bid_ask_ratio': 매수/매도 비율,
                'orderbook_units': [{'ask_price', 'bid_price', 'ask_size', 'bid_size'}, ...]
            }
        """
        symbol = symbol or settings.trade_symbol
        
        try:
            orderbook = pyupbit.get_orderbook(symbol)
            
            # 1. 리스트인 경우 (일반적인 경우)
            if isinstance(orderbook, list) and len(orderbook) > 0:
                ob = orderbook[0]
            # 2. 딕셔너리인 경우 (단일 조회 시 등) - 에러가 아니라 정상 데이터일 수 있음
            elif isinstance(orderbook, dict):
                # 에러 메시지가 있는 경우만 에러로 처리
                if 'error' in orderbook:
                    error_msg = orderbook.get('error')
                    logger.error(f"오더북 조회 API 에러 ({symbol}): {error_msg}")
                    return None
                # 에러가 아니면 정상 데이터로 처리
                ob = orderbook
            else:
                return None
            
            # 데이터 파싱
            total_ask = ob.get('total_ask_size', 0)
            total_bid = ob.get('total_bid_size', 0)
            
            # 매수/매도 비율 계산 (0으로 나누기 방지)
            bid_ask_ratio = total_bid / total_ask if total_ask > 0 else 0
            
            result = {
                'total_ask_size': total_ask,
                'total_bid_size': total_bid,
                'bid_ask_ratio': bid_ask_ratio,
                'orderbook_units': ob.get('orderbook_units', [])
            }
            
            logger.debug(f"오더북 조회: 매수잔량={total_bid:.2f}, 매도잔량={total_ask:.2f}, 비율={bid_ask_ratio:.2f}x")
            return result

        except Exception as e:
            logger.error(f"오더북 조회 실패 ({symbol}): {e}")
            return None
    
    def get_order(self, uuid: str) -> Optional[Dict]:
        """
        주문 조회
        
        Args:
            uuid: 주문 UUID
            
        Returns:
            주문 정보
        """
        if not self.upbit:
            return None
        
        try:
            return self.upbit.get_order(uuid)
        except Exception as e:
            logger.error(f"주문 조회 실패 ({uuid}): {e}")
            return None
    
    def get_avg_buy_price(self, ticker: str) -> float:
        """
        평균 매수가 조회
        
        Args:
            ticker: 통화 (예: "BTC")
            
        Returns:
            평균 매수가
        """
        if not self.upbit:
            return 0.0
        
        try:
            return float(self.upbit.get_avg_buy_price(ticker) or 0.0)
        except Exception as e:
            logger.error(f"평균 매수가 조회 실패 ({ticker}): {e}")
            return 0.0


# Test
if __name__ == "__main__":
    # 테스트 (실제 API 키 없이)
    print("=== Upbit Client Test (without real API key) ===")
    
    # 현재가 조회 (API 키 불필요)
    price = pyupbit.get_current_price("KRW-BTC")
    print(f"BTC 현재가: ₩{price:,.0f}" if price else "현재가 조회 실패")
    
    # OHLCV 조회 (API 키 불필요)
    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=5)
    if df is not None:
        print("\n최근 5개 1시간봉:")
        print(df.tail())
