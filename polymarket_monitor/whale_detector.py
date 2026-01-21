"""
Whale Trade Detector - WebSocket based real-time monitoring
Detects $10,000+ trades and analyzes wallet age & market niche
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import TradeParams
import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


class SuspicionLevel(Enum):
    """거래 의심 수준"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class WhaleTradeInfo:
    """고래 거래 정보"""
    trade_id: str
    market_id: str
    market_question: str
    wallet_address: str
    amount_usd: float
    side: str  # "BUY" or "SELL"
    price: float
    timestamp: str
    
    # Analysis results
    wallet_age_days: int
    is_new_wallet: bool
    market_rank: int
    is_niche_market: bool
    suspicion_level: SuspicionLevel
    confidence_score: float  # 0.0 - 1.0


class WhaleDetector:
    """
    실시간 고래 거래 감지 시스템
    """
    
    # Detection thresholds
    WHALE_THRESHOLD = 10000  # $10,000 이상
    NEW_WALLET_DAYS = 7      # 7일 이내 신규 지갑
    TOP_MARKET_RANK = 50     # 상위 50위 밖이면 틈새 마켓
    
    # API endpoints
    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"
    
    def __init__(self):
        self.client: Optional[ClobClient] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.market_cache: Dict[str, Dict] = {}
        self.wallet_cache: Dict[str, Dict] = {}
        
    async def start(self):
        """Initialize connections"""
        # Read-only CLOB client (no auth needed for monitoring)
        self.client = ClobClient(self.CLOB_API)
        self.session = aiohttp.ClientSession()
        
        logger.info("🐋 Whale Detector initialized")
        logger.info(f"Threshold: ${self.WHALE_THRESHOLD:,}")
        logger.info(f"New wallet: {self.NEW_WALLET_DAYS} days")
        logger.info(f"Niche market: rank > {self.TOP_MARKET_RANK}")
        
    async def stop(self):
        """Cleanup"""
        if self.session:
            await self.session.close()
        logger.info("Whale Detector stopped")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_wallet_info(self, address: str) -> Dict:
        """
        Get wallet creation date from Gamma API
        
        Returns:
            {
                'address': str,
                'creation_date': str (ISO 8601),
                'age_days': int
            }
        """
        # Check cache
        if address in self.wallet_cache:
            return self.wallet_cache[address]
        
        try:
            url = f"{self.GAMMA_API}/public-profile/{address}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    creation_date = data.get('creationDate')
                    
                    if creation_date:
                        created = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
                        age_days = (datetime.now(created.tzinfo) - created).days
                    else:
                        # No creation date = assume old wallet
                        age_days = 999
                    
                    wallet_info = {
                        'address': address,
                        'creation_date': creation_date,
                        'age_days': age_days
                    }
                    
                    # Cache for 1 hour
                    self.wallet_cache[address] = wallet_info
                    
                    return wallet_info
                else:
                    logger.warning(f"Failed to get wallet info for {address}: {response.status}")
                    return {'address': address, 'age_days': 999}
                    
        except Exception as e:
            logger.error(f"Error getting wallet info: {e}")
            return {'address': address, 'age_days': 999}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_market_rank(self, market_id: str) -> int:
        """
        Get market rank by volume
        
        Returns:
            Rank (1 = highest volume)
        """
        try:
            # Get all markets sorted by volume
            url = f"{self.GAMMA_API}/markets"
            params = {
                'limit': 100,
                'order': 'volume24hr',
                'ascending': False
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    markets = await response.json()
                    
                    # Find rank
                    for idx, market in enumerate(markets, 1):
                        if market.get('id') == market_id or market.get('condition_id') == market_id:
                            return idx
                    
                    # Not in top 100 = niche market
                    return 999
                else:
                    logger.warning(f"Failed to get market rank: {response.status}")
                    return 999
                    
        except Exception as e:
            logger.error(f"Error getting market rank: {e}")
            return 999
    
    async def get_market_info(self, market_id: str) -> Dict:
        """Get market details"""
        if market_id in self.market_cache:
            return self.market_cache[market_id]
        
        try:
            url = f"{self.GAMMA_API}/markets/{market_id}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.market_cache[market_id] = data
                    return data
                else:
                    return {'question': 'Unknown Market'}
                    
        except Exception as e:
            logger.error(f"Error getting market info: {e}")
            return {'question': 'Unknown Market'}
    
    def calculate_suspicion_level(
        self,
        amount: float,
        wallet_age_days: int,
        market_rank: int
    ) -> tuple[SuspicionLevel, float]:
        """
        Calculate suspicion level and confidence score
        
        Returns:
            (SuspicionLevel, confidence_score)
        """
        score = 0.0
        
        # Factor 1: Amount (0-0.3)
        if amount >= 100000:  # $100k+
            score += 0.3
        elif amount >= 50000:  # $50k+
            score += 0.2
        elif amount >= 10000:  # $10k+
            score += 0.1
        
        # Factor 2: Wallet age (0-0.4)
        if wallet_age_days <= 3:  # 3일 이내
            score += 0.4
        elif wallet_age_days <= 7:  # 7일 이내
            score += 0.3
        elif wallet_age_days <= 14:  # 2주 이내
            score += 0.1
        
        # Factor 3: Market niche (0-0.3)
        if market_rank > 100:  # 매우 틈새
            score += 0.3
        elif market_rank > 50:  # 틈새
            score += 0.2
        elif market_rank > 20:  # 중간
            score += 0.1
        
        # Determine level
        if score >= 0.7:
            level = SuspicionLevel.HIGH
        elif score >= 0.4:
            level = SuspicionLevel.MEDIUM
        else:
            level = SuspicionLevel.LOW
        
        return level, score
    
    async def analyze_trade(self, trade: Dict) -> Optional[WhaleTradeInfo]:
        """
        Analyze a single trade
        
        Returns:
            WhaleTradeInfo if suspicious, None otherwise
        """
        try:
            # Extract trade info
            amount_usd = float(trade.get('size', 0)) * float(trade.get('price', 0))
            
            # Filter: Only $10k+ trades
            if amount_usd < self.WHALE_THRESHOLD:
                return None
            
            wallet_address = trade.get('maker', '') or trade.get('taker', '')
            market_id = trade.get('market', '') or trade.get('asset_id', '')
            
            # Get wallet age
            wallet_info = await self.get_wallet_info(wallet_address)
            wallet_age_days = wallet_info['age_days']
            is_new_wallet = wallet_age_days <= self.NEW_WALLET_DAYS
            
            # Get market rank
            market_rank = await self.get_market_rank(market_id)
            is_niche_market = market_rank > self.TOP_MARKET_RANK
            
            # Get market details
            market_info = await self.get_market_info(market_id)
            market_question = market_info.get('question', 'Unknown')
            
            # Calculate suspicion
            suspicion_level, confidence_score = self.calculate_suspicion_level(
                amount_usd,
                wallet_age_days,
                market_rank
            )
            
            # Create whale trade info
            whale_trade = WhaleTradeInfo(
                trade_id=trade.get('id', ''),
                market_id=market_id,
                market_question=market_question,
                wallet_address=wallet_address,
                amount_usd=amount_usd,
                side=trade.get('side', 'UNKNOWN'),
                price=float(trade.get('price', 0)),
                timestamp=trade.get('timestamp', datetime.now().isoformat()),
                wallet_age_days=wallet_age_days,
                is_new_wallet=is_new_wallet,
                market_rank=market_rank,
                is_niche_market=is_niche_market,
                suspicion_level=suspicion_level,
                confidence_score=confidence_score
            )
            
            logger.info(
                f"🐋 Whale detected: ${amount_usd:,.0f} | "
                f"Wallet age: {wallet_age_days}d | "
                f"Market rank: {market_rank} | "
                f"Suspicion: {suspicion_level.value.upper()} ({confidence_score:.2f})"
            )
            
            return whale_trade
            
        except Exception as e:
            logger.error(f"Error analyzing trade: {e}")
            return None
    
    async def monitor_trades(self) -> AsyncGenerator[WhaleTradeInfo, None]:
        """
        Monitor trades in real-time
        
        Yields:
            WhaleTradeInfo for suspicious trades
        """
        logger.info("🔍 Starting trade monitoring...")
        
        last_check = datetime.now()
        
        while True:
            try:
                # Get recent trades (last 5 minutes)
                trades = self.client.get_trades(
                    TradeParams(
                        # Filter by recent trades
                    )
                )
                
                for trade in trades:
                    # Analyze trade
                    whale_trade = await self.analyze_trade(trade)
                    
                    if whale_trade:
                        yield whale_trade
                
                # Wait before next check (avoid rate limits)
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)


# Test function
async def test_detector():
    """Test whale detector"""
    detector = WhaleDetector()
    await detector.start()
    
    try:
        async for whale_trade in detector.monitor_trades():
            logger.info(f"Detected: {whale_trade}")
            
            # Test only first detection
            break
    finally:
        await detector.stop()


if __name__ == "__main__":
    asyncio.run(test_detector())
