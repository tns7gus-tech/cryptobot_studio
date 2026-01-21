"""
Main Polymarket Whale Bot
Orchestrates whale detection, AI analysis, risk management, and auto-trading
"""
import asyncio
import os
from datetime import datetime
from typing import Literal
from loguru import logger
import sys

from whale_detector import WhaleDetector
from gemini_analyzer import GeminiAnalyzer
from risk_manager import RiskManager
from auto_trader import AutoTrader
from telegram_notifier import TelegramNotifier
from config import settings


# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=os.getenv('LOG_LEVEL', 'INFO')
)
logger.add(
    "logs/whale_bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)


class PolymarketWhaleBot:
    """
    24/7 Polymarket Whale Trading Bot
    """
    
    def __init__(self, mode: Literal["semi", "full"] = "semi"):
        self.mode = mode
        
        # Initialize components
        self.detector = WhaleDetector()
        self.ai_analyzer = GeminiAnalyzer()
        self.risk_manager = RiskManager()
        self.trader = AutoTrader(mode=mode)
        self.notifier = TelegramNotifier()
        
        logger.info(f"🤖 Polymarket Whale Bot initialized (mode: {mode})")
    
    async def start(self):
        """Initialize all components"""
        logger.info("🚀 Starting Polymarket Whale Bot...")
        
        # Start detector
        await self.detector.start()
        
        # Start notifier
        await self.notifier.start()
        
        # Send startup message
        await self.notifier.send_startup_message(mode=self.mode)
        
        logger.info("✅ All components started")
    
    async def stop(self):
        """Cleanup"""
        logger.info("Shutting down...")
        
        await self.detector.stop()
        
        logger.info("✅ Shutdown complete")
    
    async def process_whale_trade(self, whale_trade):
        """
        Process detected whale trade
        
        1. AI analysis
        2. Risk check
        3. Execute trade (if approved)
        4. Send notifications
        5. Log results
        """
        try:
            logger.info(f"🐋 Processing whale trade: ${whale_trade.amount_usd:,.0f}")
            
            # Step 1: AI Analysis
            logger.info("🤖 Running AI analysis...")
            ai_analysis = await self.ai_analyzer.analyze_whale_trade(whale_trade)
            
            logger.info(
                f"AI Result: {ai_analysis['recommendation']} "
                f"(confidence: {ai_analysis['confidence']:.2f})"
            )
            
            # Step 2: Send whale alert
            await self.notifier.send_whale_alert(whale_trade, ai_analysis)
            
            # Step 3: Decide whether to trade
            should_trade = (
                ai_analysis['recommendation'] == 'BET' and
                ai_analysis['confidence'] >= 0.7  # 70% confidence threshold
            )
            
            if not should_trade:
                logger.info(f"⏭️ Skipping trade (recommendation: {ai_analysis['recommendation']})")
                return
            
            # Step 4: Risk check
            can_trade, reason = self.risk_manager.can_trade(
                amount=self.risk_manager.MAX_BET_PER_TRADE
            )
            
            if not can_trade:
                logger.warning(f"🛑 Risk check failed: {reason}")
                await self.notifier.send_message(f"⚠️ Trade blocked: {reason}")
                return
            
            # Step 5: Execute trade
            logger.info("🎯 Executing trade...")
            trade_result = await self.trader.execute_trade(
                whale_trade,
                ai_analysis,
                bet_amount=self.risk_manager.MAX_BET_PER_TRADE
            )
            
            # Step 6: Record trade
            if trade_result.success or self.mode == "semi":
                # Estimate profit (will be updated later)
                estimated_profit = 0.0  # Unknown until trade settles
                
                self.risk_manager.record_trade(
                    amount=trade_result.amount,
                    profit=estimated_profit
                )
            
            # Step 7: Send execution notification
            await self.notifier.send_trade_executed(
                whale_trade,
                trade_result,
                ai_analysis
            )
            
            logger.success(f"✅ Whale trade processed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error processing whale trade: {e}", exc_info=True)
            await self.notifier.send_message(f"⚠️ Error: {str(e)[:200]}")
    
    async def send_daily_report(self):
        """Send daily performance report"""
        try:
            stats = self.risk_manager.get_daily_stats()
            stats_dict = {
                'total_bets': stats.total_bets,
                'total_wagered': stats.total_wagered,
                'total_profit': stats.total_profit,
                'win_count': stats.win_count,
                'loss_count': stats.loss_count,
                'win_rate': (
                    stats.win_count / stats.total_bets
                    if stats.total_bets > 0
                    else 0.0
                )
            }
            
            # Generate AI report
            ai_report = await self.ai_analyzer.generate_daily_report(stats_dict)
            
            # Send report
            await self.notifier.send_daily_report(stats_dict, ai_report)
            
            logger.info("📊 Daily report sent")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🔄 Starting monitoring loop...")
        
        last_report_date = datetime.now().date()
        
        try:
            async for whale_trade in self.detector.monitor_trades():
                # Process whale trade
                await self.process_whale_trade(whale_trade)
                
                # Check if we need to send daily report
                current_date = datetime.now().date()
                if current_date > last_report_date:
                    await self.send_daily_report()
                    last_report_date = current_date
                
                # Small delay between trades
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}", exc_info=True)
            
            # Send emergency stop
            await self.notifier.send_emergency_stop(str(e))
            self.risk_manager.emergency_stop(str(e))
    
    async def run(self):
        """Main entry point"""
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
    # Get mode from environment or default to semi
    mode = os.getenv('BOT_MODE', 'semi')
    
    if mode not in ['semi', 'full']:
        logger.error(f"Invalid BOT_MODE: {mode}. Must be 'semi' or 'full'")
        return
    
    # Create and run bot
    bot = PolymarketWhaleBot(mode=mode)
    await bot.run()


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # Run bot
    asyncio.run(main())
