"""
Telegram notification bot
Sends alerts for anomalies and high-value signals
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
from config import settings


class TelegramNotifier:
    """
    Sends formatted alerts to Telegram
    """
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.chat_id = settings.telegram_chat_id
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def start(self):
        """Initialize Telegram bot"""
        self.bot = Bot(token=settings.telegram_bot_token)
        logger.info("Telegram bot initialized")
        
        # Test connection
        try:
            me = await self.bot.get_me()
            logger.info(f"Bot connected: @{me.username}")
        except TelegramError as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise
    
    async def close(self):
        """Cleanup"""
        logger.info("Telegram notifier closed")
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to the configured chat
        
        Args:
            message: Message text (supports HTML formatting)
            parse_mode: Telegram parse mode (HTML or Markdown)
            
        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Message sent to Telegram")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_maps_alert(self, data: Dict) -> bool:
        """
        Send Google Maps anomaly alert
        
        Args:
            data: Scraper result with anomaly
        """
        try:
            place_name = data.get('place_name', 'Unknown')
            current = data.get('current_popularity', 'N/A')
            baseline = data.get('baseline_popularity', 'N/A')
            delta = data.get('delta', 'N/A')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            message = f"""
🚨 <b>GOOGLE MAPS ALERT</b> 🚨

📍 <b>Location:</b> {place_name}
📊 <b>Current Busyness:</b> {current}%
📈 <b>Baseline:</b> {baseline}%
⚡ <b>Delta:</b> +{delta}%

🕐 <b>Time:</b> {timestamp}

⚠️ <b>Unusual activity detected!</b>
Consider checking Polymarket for related events.
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending Maps alert: {e}")
            return False
    
    async def send_polymarket_alert(self, anomaly: Dict) -> bool:
        """
        Send Polymarket anomaly alert
        
        Args:
            anomaly: Anomaly detection result
        """
        try:
            market_question = anomaly.get('market_question', 'Unknown')
            anomaly_type = anomaly.get('anomaly_type', 'unknown')
            current_prob = anomaly.get('current_probability', 'N/A')
            historical_avg = anomaly.get('historical_average', 'N/A')
            prob_change = anomaly.get('probability_change', 'N/A')
            severity = anomaly.get('severity', 'MEDIUM')
            timestamp = anomaly.get('timestamp', datetime.now().isoformat())
            
            # Emoji based on severity
            emoji = "🔴" if severity == "HIGH" else "🟡"
            
            # Type-specific messages
            type_messages = {
                "extreme_shift": "Extreme probability shift detected!",
                "insider_reversal": "⚠️ POSSIBLE INSIDER TRADING PATTERN ⚠️"
            }
            
            type_msg = type_messages.get(anomaly_type, "Anomaly detected")
            
            message = f"""
{emoji} <b>POLYMARKET ALERT</b> {emoji}

📊 <b>Market:</b> {market_question}

🎯 <b>Current Probability:</b> {current_prob:.1f}%
📉 <b>Historical Average:</b> {historical_avg:.1f}%
⚡ <b>Change:</b> {prob_change:.1f}%

🔍 <b>Type:</b> {anomaly_type}
⚠️ <b>Severity:</b> {severity}

💡 <b>{type_msg}</b>

🕐 <b>Time:</b> {timestamp}

🎲 Consider entering position if signal confirms.
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending Polymarket alert: {e}")
            return False
    
    async def send_combined_alert(self, maps_data: Dict, polymarket_data: Dict) -> bool:
        """
        Send combined alert when both signals align
        
        Args:
            maps_data: Google Maps anomaly
            polymarket_data: Polymarket anomaly
        """
        try:
            message = f"""
🔥🔥🔥 <b>COMBINED SIGNAL ALERT</b> 🔥🔥🔥

<b>BOTH INDICATORS TRIGGERED!</b>

📍 <b>Google Maps:</b>
{maps_data.get('place_name', 'Unknown')} showing {maps_data.get('current_popularity', 'N/A')}% busyness
(+{maps_data.get('delta', 'N/A')}% above normal)

📊 <b>Polymarket:</b>
{polymarket_data.get('market_question', 'Unknown')}
Probability: {polymarket_data.get('current_probability', 'N/A'):.1f}%
Change: {polymarket_data.get('probability_change', 'N/A'):.1f}%

⚡ <b>HIGH CONFIDENCE SIGNAL</b>
🎯 <b>ACTION RECOMMENDED</b>

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending combined alert: {e}")
            return False
    
    async def send_whale_alert(self, whale_trade, ai_analysis: dict) -> bool:
        """
        Send whale trade detection alert
        
        Args:
            whale_trade: WhaleTradeInfo object
            ai_analysis: Gemini AI analysis result
        """
        try:
            # Emoji based on suspicion level
            level_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴"
            }
            emoji = level_emoji.get(whale_trade.suspicion_level.value, "⚪")
            
            # Recommendation emoji
            rec_emoji = {
                "BET": "🎯",
                "SKIP": "⏭️",
                "MONITOR": "👀"
            }
            rec = ai_analysis.get('recommendation', 'SKIP')
            
            message = f"""
{emoji} <b>WHALE DETECTED</b> {emoji}

💰 <b>Amount:</b> ${whale_trade.amount_usd:,.0f}
📊 <b>Side:</b> {whale_trade.side}
💵 <b>Price:</b> {whale_trade.price:.3f}

📍 <b>Market:</b> {whale_trade.market_question[:100]}

👤 <b>Wallet Analysis:</b>
• Address: <code>{whale_trade.wallet_address[:16]}...</code>
• Age: {whale_trade.wallet_age_days} days
• New wallet: {'✅ YES' if whale_trade.is_new_wallet else '❌ NO'}

📈 <b>Market Analysis:</b>
• Rank: #{whale_trade.market_rank}
• Niche market: {'✅ YES' if whale_trade.is_niche_market else '❌ NO'}

🤖 <b>AI Analysis:</b>
• Insider probability: {ai_analysis.get('confidence', 0)*100:.0f}%
• Recommendation: {rec_emoji.get(rec, '')} <b>{rec}</b>
• Reasoning: {ai_analysis.get('reasoning', 'N/A')[:200]}

⚠️ <b>Suspicion Level:</b> {whale_trade.suspicion_level.value.upper()} ({whale_trade.confidence_score:.2f})

🕐 {whale_trade.timestamp}
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending whale alert: {e}")
            return False
    
    async def send_trade_executed(self, whale_trade, trade_result, ai_analysis: dict) -> bool:
        """
        Send trade execution notification
        
        Args:
            whale_trade: WhaleTradeInfo
            trade_result: TradeResult
            ai_analysis: AI analysis
        """
        try:
            if trade_result.success:
                emoji = "✅"
                status = "SUCCESS"
            else:
                emoji = "❌"
                status = "FAILED"
            
            message = f"""
{emoji} <b>TRADE {status}</b> {emoji}

🎯 <b>Order Details:</b>
• Order ID: <code>{trade_result.order_id or 'N/A'}</code>
• Amount: ${trade_result.amount:.2f}
• Side: {trade_result.side}
• Price: {trade_result.price:.3f}

📊 <b>Market:</b> {whale_trade.market_question[:100]}

🤖 <b>AI Confidence:</b> {ai_analysis.get('confidence', 0)*100:.0f}%

{f'⚠️ <b>Error:</b> {trade_result.error}' if trade_result.error else ''}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending trade executed: {e}")
            return False
    
    async def send_daily_report(self, stats: dict, ai_report: str) -> bool:
        """
        Send daily performance report
        
        Args:
            stats: Daily statistics
            ai_report: AI-generated report
        """
        try:
            profit_emoji = "📈" if stats.get('total_profit', 0) > 0 else "📉"
            
            message = f"""
📊 <b>DAILY REPORT</b> 📊

💰 <b>Performance:</b>
• Total bets: {stats.get('total_bets', 0)}
• Total wagered: ${stats.get('total_wagered', 0):.2f}
• Net profit: {profit_emoji} ${stats.get('total_profit', 0):+.2f}
• Win rate: {stats.get('win_rate', 0)*100:.1f}%
• Wins: {stats.get('win_count', 0)} | Losses: {stats.get('loss_count', 0)}

🤖 <b>AI Analysis:</b>
{ai_report}

📅 {datetime.now().strftime('%Y-%m-%d')}
"""
            
            return await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False
    
    async def send_emergency_stop(self, reason: str) -> bool:
        """Send emergency stop notification"""
        message = f"""
🚨🚨🚨 <b>EMERGENCY STOP</b> 🚨🚨🚨

⚠️ <b>Reason:</b> {reason}

🛑 All trading has been halted.
📞 Please check the system immediately.

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return await self.send_message(message)
    
    async def send_startup_message(self, mode: str = "semi") -> bool:
        """Send startup notification"""
        mode_text = "🔴 FULL AUTO" if mode == "full" else "🟡 SEMI AUTO"
        
        message = f"""
✅ <b>Polymarket Whale Bot Started</b>

🤖 <b>Mode:</b> {mode_text}
🐋 <b>Whale threshold:</b> $10,000+
📊 <b>Max daily bets:</b> 5
💰 <b>Max bet amount:</b> $50
📉 <b>Max daily loss:</b> $200

🔍 <b>Detection criteria:</b>
• New wallets (≤7 days)
• Niche markets (rank >50)
• Large trades ($10k+)

🤖 <b>AI:</b> Gemini Pro analysis enabled

🚀 Ready to hunt whales!
"""
        return await self.send_message(message)


# Test function
async def test_notifier():
    """Test Telegram notifications"""
    async with TelegramNotifier() as notifier:
        # Test startup message
        await notifier.send_startup_message()
        
        # Test Maps alert
        test_maps_data = {
            "place_name": "Domino's Pizza (Pentagon City)",
            "current_popularity": 85,
            "baseline_popularity": 30,
            "delta": 55,
            "timestamp": datetime.now().isoformat()
        }
        await notifier.send_maps_alert(test_maps_data)
        
        # Test Polymarket alert
        test_polymarket_data = {
            "market_question": "Will there be US military action in 2024?",
            "anomaly_type": "insider_reversal",
            "current_probability": 5.0,
            "historical_average": 95.0,
            "probability_change": 90.0,
            "severity": "HIGH",
            "timestamp": datetime.now().isoformat()
        }
        await notifier.send_polymarket_alert(test_polymarket_data)


if __name__ == "__main__":
    asyncio.run(test_notifier())
