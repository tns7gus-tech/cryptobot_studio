"""
CryptoBot Studio - Backtest Optimizer
과거 데이터 기반 파라미터 최적화 시스템

기능:
1. 과거 OHLCV 데이터로 백테스트 실행
2. Grid Search로 최적 파라미터 탐색
3. 결과 저장 및 리포트 생성
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import json
import os

import pyupbit

from strategies import ICTStrategy, Signal
from indicators import detect_order_block, detect_fvg, detect_liquidity_pool


@dataclass
class BacktestResult:
    """백테스트 결과 (확장판)"""
    params: Dict[str, Any]
    total_trades: int
    win_count: int
    loss_count: int
    total_profit_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    avg_profit_per_trade: float
    # 확장 지표
    sortino_ratio: float = 0.0  # 하방 변동성 기준
    calmar_ratio: float = 0.0   # 수익/최대손실
    profit_factor: float = 0.0  # 총이익/총손실
    
    def __str__(self):
        return (
            f"📊 백테스트 결과\n"
            f"   파라미터: {self.params}\n"
            f"   거래 수: {self.total_trades}\n"
            f"   승률: {self.win_rate:.1%}\n"
            f"   총 수익: {self.total_profit_pct:+.2f}%\n"
            f"   최대 손실폭: {self.max_drawdown_pct:.2f}%\n"
            f"   평균 수익/거래: {self.avg_profit_per_trade:.3f}%\n"
            f"   Sharpe: {self.sharpe_ratio:.2f} | Sortino: {self.sortino_ratio:.2f}\n"
            f"   Calmar: {self.calmar_ratio:.2f} | PF: {self.profit_factor:.2f}"
        )


@dataclass
class Trade:
    """거래 기록"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    profit_pct: float
    signal_reason: str


class BacktestEngine:
    """
    백테스트 엔진
    
    과거 데이터로 전략을 시뮬레이션하고 성과를 측정합니다.
    """
    
    def __init__(
        self,
        initial_capital: float = 1_000_000,  # 초기 자본금 (KRW)
        fee_rate: float = 0.0005,  # 수수료 0.05%
        slippage_rate: float = 0.002  # 슬리피지 0.2%
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        strategy: ICTStrategy,
        position_size_ratio: float = 0.3
    ) -> BacktestResult:
        """
        백테스트 실행
        
        Args:
            df: OHLCV DataFrame (시간순 정렬)
            strategy: 테스트할 전략
            position_size_ratio: 포지션 크기 비율
            
        Returns:
            BacktestResult
        """
        if df is None or len(df) < 50:
            return BacktestResult(
                params={},
                total_trades=0,
                win_count=0,
                loss_count=0,
                total_profit_pct=0,
                max_drawdown_pct=0,
                sharpe_ratio=0,
                win_rate=0,
                avg_profit_per_trade=0
            )
        
        trades: List[Trade] = []
        capital = self.initial_capital
        peak_capital = capital
        max_drawdown = 0
        
        in_position = False
        entry_price = 0
        entry_time = None
        entry_reason = ""
        
        # 시간 인덱스 확보
        df = df.reset_index()
        
        for i in range(50, len(df)):
            # 현재까지의 데이터로 분석
            window_df = df.iloc[:i+1].set_index('index')
            current_row = df.iloc[i]
            current_price = current_row['close']
            current_time = current_row['index'] if 'index' in df.columns else datetime.now()
            
            # 전략 분석
            signal = strategy.analyze(
                ohlcv_df=window_df,
                current_price=current_price,
                entry_price=entry_price if in_position else None,
                in_position=in_position
            )
            
            if not in_position and signal.action == "BUY" and signal.confidence >= 0.7:
                # 진입
                # 슬리피지 적용 (더 비싸게 삼)
                actual_entry = current_price * (1 + self.slippage_rate)
                # 수수료
                fee = actual_entry * self.fee_rate
                
                in_position = True
                entry_price = actual_entry + fee
                entry_time = current_time
                entry_reason = signal.reason
                
            elif in_position and signal.action == "SELL":
                # 청산
                # 슬리피지 적용 (더 싸게 팔림)
                actual_exit = current_price * (1 - self.slippage_rate)
                # 수수료
                fee = actual_exit * self.fee_rate
                exit_price = actual_exit - fee
                
                # 수익률 계산
                profit_pct = ((exit_price - entry_price) / entry_price) * 100
                
                # 거래 기록
                trades.append(Trade(
                    entry_time=entry_time,
                    exit_time=current_time,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    profit_pct=profit_pct,
                    signal_reason=entry_reason
                ))
                
                # 자본 업데이트
                trade_amount = capital * position_size_ratio
                profit_krw = trade_amount * (profit_pct / 100)
                capital += profit_krw
                
                # 최대 손실폭 업데이트
                if capital > peak_capital:
                    peak_capital = capital
                drawdown = ((peak_capital - capital) / peak_capital) * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                
                # 포지션 리셋
                in_position = False
                entry_price = 0
                entry_time = None
        
        # 결과 집계
        total_trades = len(trades)
        win_count = sum(1 for t in trades if t.profit_pct > 0)
        loss_count = total_trades - win_count
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        total_profit_pct = ((capital - self.initial_capital) / self.initial_capital) * 100
        avg_profit = sum(t.profit_pct for t in trades) / total_trades if total_trades > 0 else 0
        
        # 확장 지표 계산
        sharpe = 0
        sortino = 0
        calmar = 0
        profit_factor = 0
        
        if trades:
            returns = [t.profit_pct for t in trades]
            
            # Sharpe Ratio (연환산)
            if np.std(returns) > 0:
                sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
            
            # Sortino Ratio (하방 변동성만)
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns)
                if downside_std > 0:
                    sortino = (np.mean(returns) / downside_std) * np.sqrt(252)
            
            # Calmar Ratio (수익률 / 최대손실폭)
            if max_drawdown > 0:
                calmar = total_profit_pct / max_drawdown
            
            # Profit Factor (총이익 / 총손실)
            gross_profit = sum(r for r in returns if r > 0)
            gross_loss = abs(sum(r for r in returns if r < 0))
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
        
        return BacktestResult(
            params={
                "confluence_threshold": strategy.confluence_threshold,
                "min_rr_ratio": strategy.min_rr_ratio,
                "take_profit": strategy.take_profit,
                "stop_loss": strategy.stop_loss
            },
            total_trades=total_trades,
            win_count=win_count,
            loss_count=loss_count,
            total_profit_pct=total_profit_pct,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            avg_profit_per_trade=avg_profit,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            profit_factor=profit_factor
        )


class ParameterOptimizer:
    """
    파라미터 최적화기
    
    Grid Search를 통해 최적의 전략 파라미터를 찾습니다.
    """
    
    def __init__(self, backtest_engine: BacktestEngine = None):
        self.engine = backtest_engine or BacktestEngine()
        self.results: List[BacktestResult] = []
    
    def grid_search(
        self,
        df: pd.DataFrame,
        param_grid: Dict[str, List[Any]]
    ) -> Tuple[BacktestResult, List[BacktestResult]]:
        """
        Grid Search 실행
        
        Args:
            df: 백테스트용 OHLCV DataFrame
            param_grid: 파라미터 그리드
                예: {
                    "confluence_threshold": [60, 70, 80],
                    "take_profit": [1.0, 1.5, 2.0],
                    "stop_loss": [0.5, 0.75, 1.0]
                }
                
        Returns:
            (최적 결과, 전체 결과 리스트)
        """
        from itertools import product
        
        # 파라미터 조합 생성
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))
        
        logger.info(f"🔍 Grid Search 시작: {len(combinations)}개 조합 테스트")
        
        self.results = []
        
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            
            # 전략 생성
            strategy = ICTStrategy(
                confluence_threshold=params.get("confluence_threshold", 80),
                min_rr_ratio=params.get("min_rr_ratio", 2.0),
                take_profit=params.get("take_profit", 2.0),
                stop_loss=params.get("stop_loss", 1.0)
            )
            
            # 백테스트 실행
            result = self.engine.run_backtest(df, strategy)
            result.params = params  # 파라미터 저장
            self.results.append(result)
            
            if (i + 1) % 10 == 0:
                logger.info(f"   진행: {i + 1}/{len(combinations)}")
        
        # 최적 결과 선택 (Total Profit 기준)
        if not self.results:
            return None, []
        
        # 정렬: 수익률 > 승률 > Sharpe
        sorted_results = sorted(
            self.results,
            key=lambda r: (r.total_profit_pct, r.win_rate, r.sharpe_ratio),
            reverse=True
        )
        
        best = sorted_results[0]
        logger.success(f"✅ 최적 파라미터 발견:\n{best}")
        
        return best, sorted_results
    
    def save_results(self, filepath: str = "optimization_results.json"):
        """결과 저장"""
        data = []
        for r in self.results:
            data.append({
                "params": r.params,
                "total_trades": r.total_trades,
                "win_rate": r.win_rate,
                "total_profit_pct": r.total_profit_pct,
                "max_drawdown_pct": r.max_drawdown_pct,
                "sharpe_ratio": r.sharpe_ratio
            })
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📁 결과 저장: {filepath}")


def quick_optimize(
    symbol: str = "KRW-ETH",
    days: int = 30,
    interval: str = "minute60"
) -> Optional[BacktestResult]:
    """
    빠른 최적화 실행
    
    Args:
        symbol: 마켓 심볼
        days: 테스트 기간 (일)
        interval: 캔들 간격
        
    Returns:
        최적 백테스트 결과
    """
    logger.info(f"📊 {symbol} 최적화 시작 ({days}일 {interval})")
    
    # 데이터 수집
    count = days * 24 if "minute60" in interval else days * 24 * 12
    count = min(count, 200)  # API 제한
    
    df = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
    
    if df is None:
        logger.error("데이터 조회 실패")
        return None
    
    # 파라미터 그리드 (작은 범위로 빠른 테스트)
    param_grid = {
        "confluence_threshold": [50, 60, 70, 80],
        "take_profit": [1.0, 1.5, 2.0, 2.5],
        "stop_loss": [0.5, 0.75, 1.0, 1.5]
    }
    
    optimizer = ParameterOptimizer()
    best, all_results = optimizer.grid_search(df, param_grid)
    
    # 상위 5개 출력
    print("\n📌 상위 5개 결과:")
    for i, r in enumerate(all_results[:5], 1):
        print(f"{i}. {r.params} → 수익: {r.total_profit_pct:+.2f}%, 승률: {r.win_rate:.1%}")
    
    return best


# Test
if __name__ == "__main__":
    print("=== Backtest Optimizer Test ===\n")
    
    result = quick_optimize(
        symbol="KRW-ETH",
        days=14,
        interval="minute60"
    )
    
    if result:
        print(f"\n🏆 최적 결과:\n{result}")
