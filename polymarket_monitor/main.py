"""
Main orchestration script
Coordinates Google Maps scraping, Polymarket monitoring, and alerts
"""
import asyncio
from datetime import datetime, time as dt_time
from typing import List, Dict
from loguru import logger
import sys
from pathlib import Path

from config import settings
from scraper import GoogleMapsScraper
from polymarket_monitor import PolymarketMonitor
from telegram_notifier import TelegramNotifier


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)
logger.add(
    "logs/polymarket_monitor_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)


class MonitorOrchestrator:
    """
    Main orchestrator that coordinates all monitoring activities
    """
    
    def __init__(self):
        self.scraper: GoogleMapsScraper = None
        self.polymarket: PolymarketMonitor = None
        self.notifier: TelegramNotifier = None
        self.baseline_data: Dict[str, float] = {}
        
    async def start(self):
        """Initialize all components"""
        logger.info("🚀 Starting Polymarket Monitor...")
        
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Initialize components
        self.scraper = GoogleMapsScraper()
        await self.scraper.start()
        
        self.polymarket = PolymarketMonitor()
        await self.polymarket.start()
        
        self.notifier = TelegramNotifier()
        await self.notifier.start()
        
        # Send startup notification
        await self.notifier.send_startup_message()
        
        logger.info("✅ All components initialized")
    
    async def stop(self):
        """Cleanup all components"""
        logger.info("Shutting down...")
        
        if self.scraper:
            await self.scraper.close()
        
        if self.polymarket:
            await self.polymarket.close()
        
        logger.info("✅ Shutdown complete")
    
    def is_alert_time(self) -> bool:
        """
        Check if current time is within alert hours
        
        Returns:
            True if we should send alerts now
        """
        now = datetime.now().time()
        
        # Parse alert times
        start_time = dt_time.fromisoformat(settings.alert_time_start)
        end_time = dt_time.fromisoformat(settings.alert_time_end)
        
        # Handle overnight periods (e.g., 22:00 - 06:00)
        if start_time > end_time:
            return now >= start_time or now <= end_time
        else:
            return start_time <= now <= end_time
    
    async def scrape_maps_data(self) -> List[Dict]:
        """
        Scrape Google Maps for all target locations
        
        Returns:
            List of scraping results
        """
        targets = settings.target_locations_list
        
        if not targets:
            logger.warning("No target locations configured!")
            return []
        
        logger.info(f"Scraping {len(targets)} locations...")
        results = await self.scraper.scrape_multiple(targets)
        
        return results
    
    def analyze_maps_anomaly(self, data: Dict) -> bool:
        """
        Analyze if Maps data shows anomaly
        
        Args:
            data: Scraper result
            
        Returns:
            True if anomaly detected
        """
        if not data.get('success'):
            return False
        
        query = data['query']
        current = data.get('current_popularity')
        
        if current is None:
            return False
        
        # Get or set baseline
        if query not in self.baseline_data:
            self.baseline_data[query] = current
            logger.info(f"Set baseline for {query}: {current}%")
            return False
        
        baseline = self.baseline_data[query]
        delta = current - baseline
        
        # Update baseline with moving average
        self.baseline_data[query] = (baseline * 0.9) + (current * 0.1)
        
        # Check anomaly threshold
        if delta > settings.anomaly_threshold:
            data['baseline_popularity'] = baseline
            data['delta'] = delta
            return True
        
        return False
    
    async def monitor_loop(self):
        """
        Main monitoring loop
        """
        logger.info("🔄 Starting monitoring loop...")
        
        # Polymarket keywords to monitor
        polymarket_keywords = [
            "military",
            "white house",
            "briefing",
            "pentagon",
            "defense",
            "war",
            "strike",
            "attack"
        ]
        
        iteration = 0
        
        while True:
            try:
                iteration += 1
                logger.info(f"=== Iteration {iteration} ===")
                
                # Check if we're in alert time window
                in_alert_window = self.is_alert_time()
                logger.info(f"Alert window active: {in_alert_window}")
                
                # 1. Scrape Google Maps
                maps_results = await self.scrape_maps_data()
                
                maps_anomalies = []
                for result in maps_results:
                    if self.analyze_maps_anomaly(result):
                        logger.warning(f"🚨 Maps anomaly: {result['place_name']}")
                        maps_anomalies.append(result)
                        
                        # Send alert if in window
                        if in_alert_window:
                            await self.notifier.send_maps_alert(result)
                
                # 2. Check Polymarket
                polymarket_markets = await self.polymarket.get_markets(polymarket_keywords)
                logger.info(f"Monitoring {len(polymarket_markets)} Polymarket markets")
                
                polymarket_anomalies = []
                for market in polymarket_markets:
                    market_id = market.get('id') or market.get('condition_id')
                    if not market_id:
                        continue
                    
                    anomaly = self.polymarket.detect_anomaly(market_id, market)
                    if anomaly:
                        logger.warning(f"🚨 Polymarket anomaly: {anomaly['market_question']}")
                        polymarket_anomalies.append(anomaly)
                        
                        # Send alert
                        await self.notifier.send_polymarket_alert(anomaly)
                
                # 3. Check for combined signals
                if maps_anomalies and polymarket_anomalies:
                    logger.critical("🔥 COMBINED SIGNAL DETECTED!")
                    
                    # Send combined alert for first pair
                    await self.notifier.send_combined_alert(
                        maps_anomalies[0],
                        polymarket_anomalies[0]
                    )
                
                # Wait for next iteration
                wait_seconds = settings.scrape_interval_minutes * 60
                logger.info(f"Waiting {settings.scrape_interval_minutes} minutes until next check...")
                await asyncio.sleep(wait_seconds)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def run(self):
        """
        Main entry point
        """
        try:
            await self.start()
            await self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await self.stop()


async def main():
    """Entry point"""
    orchestrator = MonitorOrchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
