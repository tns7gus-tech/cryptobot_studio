"""
CryptoBot Studio - Main Entry Point
Orchestrates the auto trading bot
"""
import asyncio
import os
import signal
import sys
import time
from datetime import datetime
import pytz
from pathlib import Path

# Set Timezone to KST
os.environ['TZ'] = 'Asia/Seoul'
if sys.platform != 'win32':
    time.tzset()

from aiohttp import web
from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from trader import AutoTrader
from telegram_notifier import TelegramNotifier
from risk_manager import RiskManager

# KST Timezone helper for loguru
def kst_time(*args):
    return datetime.now(pytz.timezone(settings.timezone)).timetuple()

# Configure logging
logger.remove()
log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"

logger.add(
    sys.stderr,
    format=log_format,
    level=settings.log_level
)
logger.add(
    "logs/cryptobot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format=log_format
)


class CryptoBotOrchestrator:
    """
    메인 봇 오케스트레이터
    
    - 주기적으로 시장 분석
    - 신호 발생 시 거래/알림
    - 일일 리포트 발송
    """
    
    def __init__(self, check_interval: int = 300):
        """
        Args:
            check_interval: 분석 주기 (초, 기본 5분 = 300초) - 하이브리드 전략
        """
        self.check_interval = check_interval
        self.trader = AutoTrader()  # 하이브리드 전략 (ICT + Trend)
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        
        # logger.add(telegram_sink, level="INFO", format="{message}")
        
        self.running = False
        self._last_report_date = None
        
        logger.info("🤖 CryptoBot Studio 초기화 완료")
    
    async def start(self):
        """컴포넌트 초기화"""
        await self.trader.start()
        await self.notifier.start()
        
        # 하이브리드 전략 시작 알림
        await self.notifier.send_startup_message(
            mode=settings.bot_mode, 
            top_tickers=self.trader.target_symbols
        )
        
        logger.success("🚀 CryptoBot Studio 시작! (하이브리드: ICT + Trend Following)")
    
    async def stop(self, reason: str = "정상 종료"):
        """종료 처리"""
        self.running = False
        
        # 종료 알림
        await self.notifier.send_shutdown_message(reason)
        
        await self.trader.stop()
        await self.notifier.close()
        
        logger.info(f"⏹️ CryptoBot Studio 종료: {reason}")
    
    def is_trading_time(self) -> bool:
        """
        거래 가능 시간 체크
        
        암호화폐는 24시간 거래 가능하므로 항상 True
        필요 시 특정 시간대만 거래하도록 수정 가능
        """
        return True
    
    async def _send_daily_report(self):
        """일일 리포트 발송"""
        today = datetime.now().date()
        
        # 이미 오늘 리포트 발송했으면 스킵
        if self._last_report_date == today:
            return
        
        stats = self.risk_manager.get_daily_stats()
        await self.notifier.send_daily_report(stats.to_dict())
        
        self._last_report_date = today
        logger.info("📊 일일 리포트 발송 완료")
    
    async def _check_daily_report(self):
        """매일 자정에 리포트 발송"""
        now = datetime.now()
        
        # 00:00 ~ 00:05 사이에 리포트 발송
        if now.hour == 0 and now.minute < 5:
            await self._send_daily_report()
    
    async def monitor_loop(self):
        """
        메인 모니터링 루프 (멀티 심볼)
        """
        logger.info(f"📡 모니터링 시작 (주기: {self.check_interval}초)")
        
        while self.running:
            try:
                # 거래 가능 시간 체크
                if not self.is_trading_time():
                    logger.debug("⏰ 거래 시간 외")
                    await asyncio.sleep(60)
                    continue
                
                # 거래 가능 여부 체크
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.warning(f"⚠️ 거래 불가: {reason}")
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # 분석 및 거래 실행 (멀티 심볼)
                results = await self.trader.run_once()
                
                # 결과 로깅
                for result in results:
                    if result.success:
                        if result.action not in ["HOLD", "ANALYZE"]:
                            logger.success(f"✅ {result}")
                    else:
                        if result.error:
                            logger.warning(f"⚠️ {result}")
                
                # 일일 리포트 체크
                await self._check_daily_report()
                
                # 다음 체크까지 대기
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 모니터링 취소됨")
                break
            except Exception as e:
                logger.error(f"❌ 모니터링 에러: {e}")
                await self.notifier.send_error_alert(str(e))
                await asyncio.sleep(60)  # 에러 시 1분 대기
    
    async def run(self):
        """메인 실행"""
        self.running = True
        
        # 시그널 핸들러 등록
        def signal_handler(sig, frame):
            logger.info(f"📴 시그널 수신: {sig}")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await self.start()
            await self.monitor_loop()
        finally:
            await self.stop()


async def main():
    """Entry point"""
    logger.info("=" * 50)
    logger.info("🚀 CryptoBot Studio v0.1.0")
    logger.info("=" * 50)
    
    # Proxy 설정 (고정 IP)
    if settings.proxy_url:
        os.environ["HTTP_PROXY"] = settings.proxy_url
        os.environ["HTTPS_PROXY"] = settings.proxy_url
        
        # 로깅 시 비밀번호 마스킹
        masked_proxy = settings.proxy_url
        if "@" in settings.proxy_url:
            protocol, auth_host = settings.proxy_url.split("://", 1)
            credentials, host = auth_host.split("@", 1)
            masked_proxy = f"{protocol}://*****:*****@{host}"
            
        logger.info(f"🌐 Proxy 설정됨: {masked_proxy}")
    
    # 설정 출력
    target_symbols = settings.ict_target_symbols
    logger.info(f"📊 거래 대상: {target_symbols} (BTC 제외)")
    logger.info(f"💰 1회 금액: ₩{settings.trade_amount:,.0f}")
    logger.info(f"⚙️ 모드: {settings.bot_mode}")
    logger.info(f"📈 전략: 하이브리드 (ICT 고승률 + 추세 고빈도)")
    logger.info(f"   - ICT: Confluence 80점+, 익절 +2%, 손절 -1%")
    logger.info(f"   - 추세: RSI+EMA, 익절 +0.3%, 손절 -0.5%")
    logger.info("")
    
    # 5분 주기로 분석 (하이브리드 전략)
    orchestrator = CryptoBotOrchestrator(check_interval=300)
    
    # Cloud Run 헬스체크용 HTTP 서버
    async def health_check(request):
        return web.Response(text="OK", status=200)
    
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    # HTTP 서버 시작 (Cloud Run PORT 환경변수 사용)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 HTTP 서버 시작 (포트: {port})")
    
    # 서버 안정화를 위해 잠시 대기 (헬스체크 응답성 확보)
    await asyncio.sleep(2)
    
    # 봇 실행
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())

