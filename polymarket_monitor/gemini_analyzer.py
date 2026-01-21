"""
Google AI Integration
Uses Gemini Pro for advanced trade pattern analysis
"""
import os
from typing import Dict, Optional
import google.generativeai as genai
from loguru import logger

from whale_detector import WhaleTradeInfo, SuspicionLevel


class GeminiAnalyzer:
    """
    Gemini AI를 사용한 고급 거래 패턴 분석
    """
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY not found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        logger.info("🤖 Gemini AI Analyzer initialized")
    
    async def analyze_whale_trade(self, whale_trade: WhaleTradeInfo) -> Dict:
        """
        Analyze whale trade with Gemini AI
        
        Returns:
            {
                'is_insider': bool,
                'confidence': float (0-1),
                'reasoning': str,
                'recommendation': str ('BET', 'SKIP', 'MONITOR')
            }
        """
        try:
            prompt = f"""
당신은 Polymarket 거래 패턴 분석 전문가입니다.

다음 거래를 분석하여 내부자 거래 가능성을 판단하세요:

**거래 정보:**
- 금액: ${whale_trade.amount_usd:,.2f}
- 방향: {whale_trade.side}
- 가격: {whale_trade.price:.3f}
- 마켓: {whale_trade.market_question}

**지갑 분석:**
- 지갑 주소: {whale_trade.wallet_address[:10]}...
- 생성일: {whale_trade.wallet_age_days}일 전
- 신규 지갑 여부: {'예' if whale_trade.is_new_wallet else '아니오'}

**마켓 분석:**
- 거래량 순위: {whale_trade.market_rank}위
- 틈새 마켓 여부: {'예' if whale_trade.is_niche_market else '아니오'}

**초기 의심도:**
- 수준: {whale_trade.suspicion_level.value.upper()}
- 점수: {whale_trade.confidence_score:.2f}

다음 형식으로 JSON 응답하세요:
{{
    "is_insider": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "상세한 분석 이유 (한국어)",
    "recommendation": "BET/SKIP/MONITOR",
    "key_factors": ["요인1", "요인2", "요인3"]
}}

**판단 기준:**
1. 신규 지갑 + 대량 거래 + 틈새 마켓 = 내부자 가능성 높음
2. 가격이 극단적(0.01 이하 또는 0.99 이상)이면 확신 거래
3. 거래량 순위가 낮은 마켓일수록 정보 우위 가능성 높음

JSON만 응답하세요:
"""
            
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            import json
            result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
            
            logger.info(
                f"🤖 AI Analysis: {result['recommendation']} "
                f"(confidence: {result['confidence']:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            
            # Fallback to rule-based
            return {
                'is_insider': whale_trade.suspicion_level == SuspicionLevel.HIGH,
                'confidence': whale_trade.confidence_score,
                'reasoning': "AI 분석 실패 - 규칙 기반 판단 사용",
                'recommendation': 'SKIP',
                'key_factors': []
            }
    
    async def generate_daily_report(self, stats: Dict) -> str:
        """
        Generate daily performance report
        
        Args:
            stats: Daily statistics
            
        Returns:
            Formatted report text
        """
        try:
            prompt = f"""
다음 일일 거래 통계를 바탕으로 성과 리포트를 작성하세요:

**통계:**
- 총 베팅 횟수: {stats.get('total_bets', 0)}회
- 총 베팅 금액: ${stats.get('total_wagered', 0):.2f}
- 순이익: ${stats.get('total_profit', 0):+.2f}
- 승률: {stats.get('win_rate', 0)*100:.1f}%
- 승: {stats.get('win_count', 0)}회
- 패: {stats.get('loss_count', 0)}회

**요청사항:**
1. 오늘의 성과 요약 (3줄)
2. 주요 성공/실패 요인
3. 내일의 개선 방향

한국어로 작성하고, 이모지를 적절히 사용하세요.
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return "리포트 생성 실패"


# Test
if __name__ == "__main__":
    import asyncio
    from whale_detector import WhaleTradeInfo, SuspicionLevel
    
    async def test():
        analyzer = GeminiAnalyzer()
        
        # Test whale trade
        test_trade = WhaleTradeInfo(
            trade_id="test123",
            market_id="market456",
            market_question="Will there be a US military strike in 2024?",
            wallet_address="0x1234567890abcdef",
            amount_usd=50000,
            side="BUY",
            price=0.05,
            timestamp="2024-01-11T22:00:00",
            wallet_age_days=3,
            is_new_wallet=True,
            market_rank=75,
            is_niche_market=True,
            suspicion_level=SuspicionLevel.HIGH,
            confidence_score=0.85
        )
        
        result = await analyzer.analyze_whale_trade(test_trade)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test())
