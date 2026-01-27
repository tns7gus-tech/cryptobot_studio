"""
CryptoBot Studio - Strategy Factory
다중 전략 관리 및 시장 적응형 전략 선택

목표: 승률 70%+ 안정성 우선
"""
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from loguru import logger

from strategies import ICTStrategy, Signal
from trend_analyzer import TrendFollowingAnalyzer, TrendSignal
from market_analyzer import MarketAnalyzer, MarketState, VolatilityRegime, TrendRegime


@dataclass
class StrategyConfig:
    """전략 설정"""
    name: str
    description: str
    confluence_threshold: int
    take_profit: float
    stop_loss: float
    min_rr_ratio: float
    position_size: float  # 자본 대비 %
    min_win_rate_target: float  # 최소 목표 승률


# 사전 정의된 전략 프로파일 (70%+ 승률 목표)
STRATEGY_PROFILES: Dict[str, StrategyConfig] = {
    # 보수적: 높은 승률, 낮은 수익
    "CONSERVATIVE": StrategyConfig(
        name="CONSERVATIVE",
        description="매우 보수적 - 확실한 기회만 진입",
        confluence_threshold=90,
        take_profit=1.0,
        stop_loss=0.5,
        min_rr_ratio=2.0,
        position_size=0.1,
        min_win_rate_target=0.75
    ),
    
    # 균형: 승률과 수익 균형
    "BALANCED": StrategyConfig(
        name="BALANCED",
        description="균형 - 승률 70% 목표",
        confluence_threshold=70,
        take_profit=1.5,
        stop_loss=0.75,
        min_rr_ratio=2.0,
        position_size=0.2,
        min_win_rate_target=0.70
    ),
    
    # ICT 최적화: 백테스트 기반
    "ICT_OPTIMIZED": StrategyConfig(
        name="ICT_OPTIMIZED",
        description="ICT 최적화 - 백테스트 결과 적용",
        confluence_threshold=60,
        take_profit=2.0,
        stop_loss=1.0,
        min_rr_ratio=2.0,
        position_size=0.25,
        min_win_rate_target=0.70
    ),
    
    # 추세 추종: 강한 추세에서만
    "TREND_ONLY": StrategyConfig(
        name="TREND_ONLY",
        description="추세 전용 - 강한 상승장에서만",
        confluence_threshold=50,
        take_profit=2.5,
        stop_loss=1.0,
        min_rr_ratio=2.5,
        position_size=0.15,
        min_win_rate_target=0.65
    ),
    
    # 레인징: 횡보장 전용
    "RANGING_MEAN_REVERSION": StrategyConfig(
        name="RANGING_MEAN_REVERSION",
        description="횡보장 평균회귀",
        confluence_threshold=80,
        take_profit=0.8,
        stop_loss=0.4,
        min_rr_ratio=2.0,
        position_size=0.15,
        min_win_rate_target=0.75
    )
}


class StrategyFactory:
    """
    전략 팩토리
    
    시장 상황에 따라 최적의 전략을 선택하고 생성합니다.
    """
    
    def __init__(self):
        self.market_analyzer = MarketAnalyzer()
        self.current_strategy: Optional[ICTStrategy] = None
        self.current_config: Optional[StrategyConfig] = None
    
    def select_strategy_for_market(self, market_state: MarketState) -> StrategyConfig:
        """
        시장 상황에 맞는 전략 선택
        
        원칙: 70%+ 승률을 위해 불확실한 상황에서는 SKIP
        """
        volatility = market_state.volatility
        trend = market_state.trend
        
        # 고변동성 → 보수적 또는 스킵
        if volatility == VolatilityRegime.HIGH:
            if trend in [TrendRegime.STRONG_UP]:
                return STRATEGY_PROFILES["CONSERVATIVE"]
            else:
                logger.info("⚠️ 고변동 비추세 시장 - 거래 스킵 권장")
                return STRATEGY_PROFILES["CONSERVATIVE"]  # 작은 포지션으로 진행
        
        # 저변동성
        if volatility == VolatilityRegime.LOW:
            if trend == TrendRegime.RANGING:
                return STRATEGY_PROFILES["RANGING_MEAN_REVERSION"]
            elif trend in [TrendRegime.STRONG_UP, TrendRegime.WEAK_UP]:
                return STRATEGY_PROFILES["BALANCED"]
            else:
                return STRATEGY_PROFILES["CONSERVATIVE"]
        
        # 중변동성 (기본)
        if trend == TrendRegime.STRONG_UP:
            return STRATEGY_PROFILES["TREND_ONLY"]
        elif trend == TrendRegime.RANGING:
            return STRATEGY_PROFILES["ICT_OPTIMIZED"]
        elif trend in [TrendRegime.WEAK_UP]:
            return STRATEGY_PROFILES["BALANCED"]
        else:
            return STRATEGY_PROFILES["CONSERVATIVE"]
    
    def create_strategy(self, config: StrategyConfig) -> ICTStrategy:
        """전략 인스턴스 생성"""
        return ICTStrategy(
            confluence_threshold=config.confluence_threshold,
            min_rr_ratio=config.min_rr_ratio,
            take_profit=config.take_profit,
            stop_loss=config.stop_loss
        )
    
    def get_optimal_strategy(self, df) -> tuple:
        """
        시장 분석 후 최적 전략 반환
        
        Returns:
            (ICTStrategy, StrategyConfig, MarketState)
        """
        market_state = self.market_analyzer.analyze(df)
        
        if market_state is None:
            # 기본 전략 반환
            config = STRATEGY_PROFILES["CONSERVATIVE"]
            strategy = self.create_strategy(config)
            return strategy, config, None
        
        config = self.select_strategy_for_market(market_state)
        strategy = self.create_strategy(config)
        
        self.current_strategy = strategy
        self.current_config = config
        
        logger.info(f"🎯 전략 선택: {config.name} ({config.description})")
        logger.debug(f"   시장: {market_state.volatility.value} / {market_state.trend.value}")
        
        return strategy, config, market_state
    
    def get_position_size(self, capital: float, config: StrategyConfig, market_state: MarketState = None) -> float:
        """
        동적 포지션 사이징
        
        시장 상황에 따라 포지션 크기 조정
        """
        base_size = capital * config.position_size
        
        if market_state:
            # 시장 분석기의 배수 적용
            base_size *= market_state.position_size_multiplier
            
            # 고변동성일수록 더 작게
            if market_state.volatility == VolatilityRegime.HIGH:
                base_size *= 0.5
            elif market_state.volatility == VolatilityRegime.LOW:
                base_size *= 1.2
        
        return base_size


def run_january_2026_backtest():
    """
    2026년 1월 백테스트 실행
    
    다중 전략 비교 및 최적 파라미터 탐색
    """
    import pyupbit
    from optimizer import BacktestEngine, ParameterOptimizer
    
    print("=" * 60)
    print("📊 2026년 1월 백테스트 (승률 70% 목표)")
    print("=" * 60)
    
    symbols = ["KRW-ETH", "KRW-SOL", "KRW-XRP"]
    engine = BacktestEngine(
        initial_capital=1_000_000,
        fee_rate=0.0005,
        slippage_rate=0.002
    )
    
    results = []
    
    for symbol in symbols:
        print(f"\n📌 {symbol} 분석 중...")
        
        # 1월 데이터 (약 27일 * 24시간 = 648캔들, API 제한으로 200개)
        df = pyupbit.get_ohlcv(symbol, interval="minute60", count=200)
        
        if df is None:
            print(f"   ❌ 데이터 조회 실패")
            continue
        
        # 시장 분석
        analyzer = MarketAnalyzer()
        market_state = analyzer.analyze(df)
        
        if market_state:
            print(f"\n   📈 시장 상태:")
            print(f"   {market_state}")
        
        # 여러 전략 프로파일 테스트
        print(f"\n   🧪 전략별 백테스트:")
        
        for profile_name, config in STRATEGY_PROFILES.items():
            strategy = ICTStrategy(
                confluence_threshold=config.confluence_threshold,
                min_rr_ratio=config.min_rr_ratio,
                take_profit=config.take_profit,
                stop_loss=config.stop_loss
            )
            
            result = engine.run_backtest(df, strategy, position_size_ratio=config.position_size)
            result.params["profile"] = profile_name
            result.params["symbol"] = symbol
            
            # 승률 70% 이상만 표시
            if result.win_rate >= 0.70 or result.total_trades == 0:
                status = "✅" if result.win_rate >= 0.70 else "⏸️"
            else:
                status = "❌"
            
            print(f"   {status} {profile_name}: 승률 {result.win_rate:.1%}, 수익 {result.total_profit_pct:+.2f}%, 거래 {result.total_trades}회")
            
            if result.total_trades > 0:
                results.append({
                    "symbol": symbol,
                    "profile": profile_name,
                    "win_rate": result.win_rate,
                    "profit": result.total_profit_pct,
                    "trades": result.total_trades,
                    "sharpe": result.sharpe_ratio,
                    "sortino": result.sortino_ratio,
                    "max_dd": result.max_drawdown_pct
                })
    
    # 요약
    print("\n" + "=" * 60)
    print("📋 종합 결과 (승률 70%+ 필터)")
    print("=" * 60)
    
    high_winrate = [r for r in results if r["win_rate"] >= 0.70]
    
    if high_winrate:
        # 승률 높은 순 정렬
        high_winrate.sort(key=lambda x: (x["win_rate"], x["profit"]), reverse=True)
        
        print("\n🏆 Top 5 고승률 전략:")
        for i, r in enumerate(high_winrate[:5], 1):
            print(f"   {i}. {r['symbol']} - {r['profile']}")
            print(f"      승률: {r['win_rate']:.1%}, 수익: {r['profit']:+.2f}%, 거래: {r['trades']}회")
    else:
        print("\n⚠️ 승률 70% 이상 달성 전략 없음")
        print("   → 파라미터 추가 최적화 필요")
    
    return results


# Test
if __name__ == "__main__":
    results = run_january_2026_backtest()
