"""
Polymarket API Monitor
Detects anomalous betting patterns and insider trading signals
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import json
from collections import defaultdict


class PolymarketMonitor:
    """
    Monitors Polymarket for suspicious betting patterns
    """
    
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.market_history: Dict[str, List[Dict]] = defaultdict(list)
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def start(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("Polymarket monitor initialized")
        
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("Polymarket monitor closed")
    
    async def get_markets(self, keywords: List[str] = None) -> List[Dict]:
        """
        Fetch markets matching keywords
        
        Args:
            keywords: List of keywords to filter (e.g., ["military", "white house"])
            
        Returns:
            List of market data
        """
        try:
            url = f"{self.GAMMA_API}/markets"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    markets = await response.json()
                    
                    # Filter by keywords if provided
                    if keywords:
                        filtered = []
                        for market in markets:
                            question = market.get('question', '').lower()
                            if any(kw.lower() in question for kw in keywords):
                                filtered.append(market)
                        return filtered
                    
                    return markets
                else:
                    logger.error(f"Failed to fetch markets: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    async def get_market_details(self, condition_id: str) -> Optional[Dict]:
        """
        Get detailed market information
        
        Args:
            condition_id: Market condition ID
            
        Returns:
            Market details including current odds
        """
        try:
            url = f"{self.GAMMA_API}/markets/{condition_id}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to fetch market {condition_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching market details: {e}")
            return None
    
    async def get_market_trades(self, condition_id: str) -> List[Dict]:
        """
        Get recent trades for a market
        
        Args:
            condition_id: Market condition ID
            
        Returns:
            List of recent trades
        """
        try:
            url = f"{self.BASE_URL}/trades"
            params = {"condition_id": condition_id}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to fetch trades: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    def detect_anomaly(self, market_id: str, current_data: Dict) -> Optional[Dict]:
        """
        Detect anomalous betting patterns
        
        Args:
            market_id: Market identifier
            current_data: Current market state
            
        Returns:
            Anomaly report if detected, None otherwise
        """
        try:
            # Get historical data for this market
            history = self.market_history[market_id]
            
            # Store current data
            history.append({
                "timestamp": datetime.now().isoformat(),
                "data": current_data
            })
            
            # Keep only last 100 data points
            if len(history) > 100:
                history.pop(0)
            
            # Need at least 5 data points for analysis
            if len(history) < 5:
                return None
            
            # Extract probabilities
            current_prob = self._extract_probability(current_data)
            if current_prob is None:
                return None
            
            # Calculate historical average
            historical_probs = [
                self._extract_probability(h['data']) 
                for h in history[:-1]
            ]
            historical_probs = [p for p in historical_probs if p is not None]
            
            if not historical_probs:
                return None
            
            avg_prob = sum(historical_probs) / len(historical_probs)
            
            # Detect extreme probability shifts
            prob_change = abs(current_prob - avg_prob)
            
            # Anomaly conditions:
            # 1. Probability shift > 30% in short time
            # 2. Extreme probabilities (>95% or <5%) that suddenly reverse
            
            is_anomaly = False
            anomaly_type = None
            
            if prob_change > 30:
                is_anomaly = True
                anomaly_type = "extreme_shift"
                
            # Check for "insider pattern": 98% -> 2% type scenarios
            if len(historical_probs) >= 3:
                recent_avg = sum(historical_probs[-3:]) / 3
                if recent_avg > 95 and current_prob < 10:
                    is_anomaly = True
                    anomaly_type = "insider_reversal"
                elif recent_avg < 5 and current_prob > 90:
                    is_anomaly = True
                    anomaly_type = "insider_reversal"
            
            if is_anomaly:
                return {
                    "market_id": market_id,
                    "market_question": current_data.get('question', 'Unknown'),
                    "anomaly_type": anomaly_type,
                    "current_probability": current_prob,
                    "historical_average": avg_prob,
                    "probability_change": prob_change,
                    "timestamp": datetime.now().isoformat(),
                    "severity": "HIGH" if prob_change > 50 else "MEDIUM"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting anomaly: {e}")
            return None
    
    def _extract_probability(self, market_data: Dict) -> Optional[float]:
        """Extract probability from market data"""
        try:
            # Polymarket uses different formats
            # Try common fields
            if 'outcomePrices' in market_data:
                prices = market_data['outcomePrices']
                if prices and len(prices) > 0:
                    return float(prices[0]) * 100
            
            if 'clobTokenIds' in market_data and 'outcomes' in market_data:
                # Use first outcome probability
                outcomes = market_data.get('outcomes', [])
                if outcomes:
                    return float(outcomes[0]) * 100
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting probability: {e}")
            return None
    
    async def monitor_markets(self, keywords: List[str], interval_seconds: int = 60) -> None:
        """
        Continuously monitor markets for anomalies
        
        Args:
            keywords: Keywords to filter markets
            interval_seconds: Polling interval
        """
        logger.info(f"Starting market monitoring with keywords: {keywords}")
        
        while True:
            try:
                markets = await self.get_markets(keywords)
                logger.info(f"Monitoring {len(markets)} markets")
                
                for market in markets:
                    market_id = market.get('id') or market.get('condition_id')
                    if not market_id:
                        continue
                    
                    # Detect anomalies
                    anomaly = self.detect_anomaly(market_id, market)
                    
                    if anomaly:
                        logger.warning(f"🚨 ANOMALY DETECTED: {json.dumps(anomaly, indent=2)}")
                        # This will be sent to Telegram in the main loop
                        yield anomaly
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)


# Test function
async def test_monitor():
    """Test Polymarket monitoring"""
    async with PolymarketMonitor() as monitor:
        markets = await monitor.get_markets(["military", "white house", "briefing"])
        print(f"Found {len(markets)} markets")
        for market in markets[:5]:
            print(f"- {market.get('question', 'Unknown')}")


if __name__ == "__main__":
    asyncio.run(test_monitor())
