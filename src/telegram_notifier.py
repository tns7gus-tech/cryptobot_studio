"""
CryptoBot Studio - Telegram Notifier
Sends trading alerts and reports to Telegram
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional
import pytz
from telegram import Bot
from telegram.error import TelegramError

from config import settings


class TelegramNotifier:
    """
    텔레그램 알림 발송
    
    - 매수/매도 체결 알림
    - 일일 리포트
    - 시작/종료 알림
    - 에러 알림
    """
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.chat_id = settings.telegram_chat_id
        self.timezone = pytz.timezone(settings.timezone)
    
    def get_now(self) -> datetime:
        """KST 현재 시간 반환"""
        return datetime.now(self.timezone)
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """Initialize Telegram bot"""
        try:
            self.bot = Bot(token=settings.telegram_bot_token)
            # 시작 시 로그는 터미널에만 남김 (순환 호출 방지)
            print("📱 Telegram 봇 초기화 완료")
        except Exception as e:
            print(f"❌ Telegram 봇 초기화 실패: {e}")
            self.bot = None
    
    async def close(self):
        """Cleanup"""
        pass
    
    async def send_message(
        self,
        message: str,
        parse_mode: Optional[str] = "HTML"
    ) -> bool:
        """
        메시지 발송
        """
        if not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            # 텔레그램 발송 실패 시 터미널에만 출력 (순환 참조 방지)
            print(f"❌ Telegram 발송 실패: {e}")
            return False
    
    async def send_buy_alert(
        self,
        symbol: str,
        price: float,
        amount: float,
        volume: float,
        gap_bottom: float = None,
        gap_top: float = None,
        stop_loss: float = None,
        strategy: str = "ORDERBOOK_SCALPING"
    ) -> bool:
        """
        매수 체결 알림
        """
        ticker = symbol.split('-')[1]  # KRW-BTC -> BTC
        message = f"🟢 [{ticker}] 매수: ₩{price:,.0f} (금액: ₩{amount:,.0f})"
        return await self.send_message(message, parse_mode=None)
    
    async def send_sell_alert(
        self,
        symbol: str,
        price: float,
        volume: float,
        total: float,
        avg_buy_price: float = None,
        profit_rate: float = None,
        gap_bottom: float = None,
        gap_top: float = None,
        is_stop_loss: bool = False,
        strategy: str = "ORDERBOOK_SCALPING"
    ) -> bool:
        """
        매도 체결 알림
        """
        ticker = symbol.split('-')[1]  # KRW-BTC -> BTC
        rate_str = "0%"
        if profit_rate is not None:
             sign = "+" if profit_rate >= 0 else ""
             rate_str = f"{sign}{profit_rate:.2f}%"
        
        emoji = "📈" if profit_rate and profit_rate >= 0 else "📉"
        message = f"🔴 [{ticker}] 매도: ₩{price:,.0f} ({emoji} {rate_str})"
        return await self.send_message(message, parse_mode=None)
    
    async def send_daily_report(
        self,
        stats: Dict
    ) -> bool:
        """
        일일 리포트 발송
        
        Args:
            stats: 일일 통계 딕셔너리
        """
        total_trades = stats.get('total_trades', 0)
        win_count = stats.get('win_count', 0)
        loss_count = stats.get('loss_count', 0)
        total_profit = stats.get('total_profit', 0)
        total_wagered = stats.get('total_wagered', 0)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        profit_emoji = "📈" if total_profit >= 0 else "📉"
        
        message = f"""
📊 <b>일일 거래 리포트</b>
━━━━━━━━━━━━━━━━━━━━━
📅 날짜: {self.get_now().strftime('%Y-%m-%d')}

💹 <b>거래 실적</b>
• 총 거래: {total_trades}회
• 승/패: {win_count}승 {loss_count}패
• 승률: {win_rate:.1f}%

💰 <b>수익 현황</b>
• 총 투자: ₩{total_wagered:,.0f}
{profit_emoji} 손익: ₩{total_profit:+,.0f}

🎯 <b>하이브리드 전략</b>
• ICT(30%): 고승률, 목표 +{settings.ict_take_profit}%
• Trend(15%): 고빈도, 목표 +{settings.trend_take_profit}%
━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return await self.send_message(message)
    
    async def send_startup_message(self, mode: str = "semi", top_tickers: list = None) -> bool:
        """
        봇 시작 알림
        
        Args:
            mode: 봇 모드 ("semi" or "full")
            top_tickers: 거래대금 상위 종목 리스트
        """
        mode_str = "🔔 알림 전용" if mode == "semi" else "🤖 자동매매"
        
        # 상위 티커 목록 포맷
        if top_tickers:
            tickers_str = ", ".join(top_tickers)
        else:
            tickers_str = "(조회 중...)"
        
        message = f"""
🚀 <b>CryptoBot Studio 시작</b>
━━━━━━━━━━━━━━━━━━━━━
⚙️ 모드: {mode_str}
📊 거래 대상 (BTC 제외):
{tickers_str}
💰 포지션 크기: ICT 30%, Trend 15%

🎯 <b>하이브리드 전략 (ICT + Trend)</b>
• ICT: Confluence 50점+, 익절 +{settings.ict_take_profit}%
• Trend: RSI+EMA 스캘핑, 익절 +{settings.trend_take_profit}%
• 목표: 일 1% 수익 달성 시 보수적 운용

🛡️ <b>리스크 관리</b>
• 일일 최대 거래: {settings.max_daily_trades}회
• 일일 손실 한도: ₩{settings.max_daily_loss:,.0f}

🕐 시작 시각: {self.get_now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return await self.send_message(message)
    
    async def send_shutdown_message(self, reason: str = "정상 종료") -> bool:
        """봇 종료 알림"""
        message = f"""
⏹️ <b>CryptoBot Studio 종료</b>
━━━━━━━━━━━━━━━━━━━━━
📝 사유: {reason}
🕐 시각: {self.get_now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return await self.send_message(message)
    
    async def send_error_alert(self, error: str) -> bool:
        """에러 알림"""
        message = f"""
⚠️ <b>에러 발생</b>
━━━━━━━━━━━━━━━━━━━━━
❌ {error}
🕐 시각: {self.get_now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return await self.send_message(message)
    
    async def send_signal_alert(
        self,
        symbol: str,
        action: str,
        reason: str,
        confidence: float,
        current_price: float,
        gap_bottom: float = None,
        gap_top: float = None,
        stop_loss: float = None
    ) -> bool:
        """
        거래 신호 알림 (Semi-auto 모드용)
        
        Args:
            symbol: 마켓 심볼
            action: 신호 종류 ("BUY" or "SELL")
            reason: 신호 발생 이유
            confidence: 신뢰도
            current_price: 현재가
            gap_bottom: FVG 갭 하단
            gap_top: FVG 갭 상단
            stop_loss: 손절가
        """
        ticker = symbol.split('-')[1]
        emoji = "🟢" if action == "BUY" else "🔴"
        action_kr = "매수" if action == "BUY" else "매도"
        
        # FVG 정보
        fvg_info = ""
        if gap_bottom and gap_top:
            fvg_info += f"📊 FVG 갭: ₩{gap_bottom:,.0f} ~ ₩{gap_top:,.0f}\n"
        if stop_loss:
            fvg_info += f"🛡️ 손절가: ₩{stop_loss:,.0f}\n"
        
        message = f"""
{emoji} <b>{action_kr} 신호 감지</b>
━━━━━━━━━━━━━━━━━━━━━
📊 {ticker}/KRW
💰 현재가: ₩{current_price:,.0f}
🎯 신뢰도: {confidence:.0%}
{fvg_info}📝 사유: {reason}
🕐 시각: {self.get_now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
<i>Semi-auto 모드: 수동 거래 필요</i>
        """.strip()
        
        return await self.send_message(message)
    
    async def send_weekly_market_report(
        self,
        market_states: dict
    ) -> bool:
        """
        주간 시장 분석 리포트 발송 (일요일 09:00)
        
        Args:
            market_states: {symbol: MarketState} 딕셔너리
        """
        # 전체 시장 방향 판단
        trends = []
        for symbol, state in market_states.items():
            if state:
                trends.append(state.trend.value)
        
        # 하락 vs 상승 vs 횡보 카운트
        up_count = sum(1 for t in trends if "UP" in t)
        down_count = sum(1 for t in trends if "DOWN" in t)
        ranging_count = sum(1 for t in trends if "RANGING" in t)
        
        # 전체 시장 판단
        if down_count >= len(trends) // 2 + 1:
            market_direction = "하락 추세"
            direction_emoji = "📉"
            recommendation = "SKIP (거래 미권장)"
            rec_emoji = "⛔"
            advice = "하락장에서 매수 전략은 손실 위험이 높습니다."
        elif up_count >= len(trends) // 2 + 1:
            market_direction = "상승 추세"
            direction_emoji = "📈"
            recommendation = "ACTIVE (적극 거래)"
            rec_emoji = "✅"
            advice = "상승장에서 ICT Confluence 전략이 효과적입니다."
        else:
            market_direction = "횡보/혼조"
            direction_emoji = "➡️"
            recommendation = "CONSERVATIVE (보수적 거래)"
            rec_emoji = "🟡"
            advice = "횡보장에서는 평균회귀 전략을 고려하세요."
        
        # 개별 코인 상태
        coin_status_lines = []
        for symbol, state in market_states.items():
            ticker = symbol.split('-')[1]
            if state:
                vol = state.volatility.value
                trend = state.trend.value
                rsi = state.rsi
                coin_status_lines.append(f"• {ticker}: {trend} (변동성: {vol}, RSI: {rsi:.1f})")
            else:
                coin_status_lines.append(f"• {ticker}: 데이터 없음")
        
        coin_status = "\n".join(coin_status_lines)
        
        message = f"""
{direction_emoji} <b>주간 시장 분석 리포트</b>
━━━━━━━━━━━━━━━━━━━━━
📅 {self.get_now().strftime('%Y-%m-%d %H:%M')} (KST)

🌍 <b>전체 시장</b>
{direction_emoji} 현재 시장은 <b>{market_direction}</b>

📊 <b>코인별 상태</b>
{coin_status}

🎯 <b>시스템 추천</b>
{rec_emoji} {recommendation}

💡 <b>조언</b>
{advice}

━━━━━━━━━━━━━━━━━━━━━
<i>시장 분석기 v1.0 | 매주 일요일 09:00</i>
        """.strip()
        
        return await self.send_message(message)


# Test
async def test_notifier():
    """Test Telegram notifications"""
    print("=== Telegram Notifier Test ===\n")
    
    notifier = TelegramNotifier()
    await notifier.start()
    
    if notifier.bot:
        # 시작 메시지 테스트
        result = await notifier.send_startup_message(mode="full")
        print(f"시작 메시지: {'성공' if result else '실패'}")
        
        # 매수 알림 테스트 (ICT FVG)
        result = await notifier.send_buy_alert(
            symbol="KRW-BTC",
            price=142000000,
            amount=10000,
            volume=0.00007042,
            gap_bottom=141098000,
            gap_top=141258000,
            stop_loss=140898000,
            strategy="ICT_FVG"
        )
        print(f"매수 알림: {'성공' if result else '실패'}")
    else:
        print("❌ Telegram 봇 초기화 실패 (API 키 확인 필요)")


if __name__ == "__main__":
    asyncio.run(test_notifier())
