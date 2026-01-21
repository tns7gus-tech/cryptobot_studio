"""
Auto Trading Engine
Executes trades based on whale signals
"""
import os
from typing import Optional, Literal
from dataclasses import dataclass

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from loguru import logger

from whale_detector import WhaleTradeInfo
from config import settings


@dataclass
class TradeResult:
    """거래 결과"""
    success: bool
    order_id: Optional[str]
    amount: float
    side: str
    price: float
    error: Optional[str] = None


class AutoTrader:
    """
    자동 거래 엔진
    - Semi-auto: 알림만
    - Full-auto: 자동 베팅
    """
    
    def __init__(
        self,
        mode: Literal["semi", "full"] = "semi",
        private_key: Optional[str] = None,
        funder_address: Optional[str] = None
    ):
        self.mode = mode
        self.client: Optional[ClobClient] = None
        
        if mode == "full":
            if not private_key:
                private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
            if not funder_address:
                funder_address = os.getenv('POLYMARKET_FUNDER_ADDRESS')
            
            if not private_key or not funder_address:
                raise ValueError(
                    "Full auto mode requires POLYMARKET_PRIVATE_KEY and POLYMARKET_FUNDER_ADDRESS"
                )
            
            # Initialize authenticated client
            self.client = ClobClient(
                "https://clob.polymarket.com",
                key=private_key,
                chain_id=137,  # Polygon
                signature_type=0,  # EOA
                funder=funder_address
            )
            
            # Set API credentials
            self.client.set_api_creds(
                self.client.create_or_derive_api_creds()
            )
            
            logger.info("🤖 Auto Trader initialized (FULL AUTO MODE)")
        else:
            logger.info("📢 Auto Trader initialized (SEMI AUTO MODE - alerts only)")
    
    async def execute_trade(
        self,
        whale_trade: WhaleTradeInfo,
        ai_analysis: dict,
        bet_amount: float = 50.0
    ) -> TradeResult:
        """
        Execute trade based on whale signal
        
        Args:
            whale_trade: Detected whale trade
            ai_analysis: Gemini AI analysis result
            bet_amount: Amount to bet (default: $50)
            
        Returns:
            TradeResult
        """
        # Semi-auto mode: no actual trading
        if self.mode == "semi":
            logger.info("📢 Semi-auto mode: Would have placed trade (skipping)")
            return TradeResult(
                success=False,
                order_id=None,
                amount=bet_amount,
                side=whale_trade.side,
                price=whale_trade.price,
                error="Semi-auto mode"
            )
        
        # Full-auto mode: execute trade
        try:
            # Determine side (follow the whale)
            side = BUY if whale_trade.side == "BUY" else SELL
            
            # Get token ID for the market
            # Note: In real implementation, need to map market_id to token_id
            token_id = whale_trade.market_id  # Simplified
            
            # Place market order
            logger.info(
                f"🎯 Placing order: {whale_trade.side} ${bet_amount:.2f} "
                f"on {whale_trade.market_question[:50]}..."
            )
            
            order = MarketOrderArgs(
                token_id=token_id,
                amount=bet_amount,
                side=side,
                order_type=OrderType.FOK  # Fill or Kill
            )
            
            signed_order = self.client.create_market_order(order)
            response = self.client.post_order(signed_order, OrderType.FOK)
            
            if response.get('status') == 'live' or response.get('success'):
                logger.success(
                    f"✅ Order placed successfully: {response.get('id')}"
                )
                
                return TradeResult(
                    success=True,
                    order_id=response.get('id'),
                    amount=bet_amount,
                    side=whale_trade.side,
                    price=whale_trade.price
                )
            else:
                logger.error(f"❌ Order failed: {response}")
                
                return TradeResult(
                    success=False,
                    order_id=None,
                    amount=bet_amount,
                    side=whale_trade.side,
                    price=whale_trade.price,
                    error=str(response)
                )
                
        except Exception as e:
            logger.error(f"❌ Error executing trade: {e}")
            
            return TradeResult(
                success=False,
                order_id=None,
                amount=bet_amount,
                side=whale_trade.side,
                price=whale_trade.price,
                error=str(e)
            )
    
    def get_balance(self) -> float:
        """Get current USDC balance"""
        if not self.client:
            return 0.0
        
        try:
            # Get balance from client
            # Note: Implement based on py-clob-client API
            return 0.0
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0


# Test
if __name__ == "__main__":
    # Test semi-auto mode
    trader = AutoTrader(mode="semi")
    print(f"Mode: {trader.mode}")
