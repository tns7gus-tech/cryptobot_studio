"""
CryptoBot Studio - OHLCV Cache
API 호출 최적화를 위한 캐싱 시스템
"""
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from loguru import logger

import pyupbit


@dataclass
class CacheEntry:
    """캐시 항목"""
    data: Any
    timestamp: float
    ttl: float  # Time To Live (seconds)
    
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        return time.time() - self.timestamp > self.ttl


class OHLCVCache:
    """
    OHLCV 데이터 캐싱
    
    API 호출 횟수를 줄이고 응답 속도를 개선합니다.
    동일한 심볼/인터벌에 대해 TTL 내 재요청 시 캐시된 데이터 반환.
    """
    
    def __init__(self, default_ttl: float = 60.0):
        """
        Args:
            default_ttl: 기본 캐시 유효 시간 (초, 기본 60초)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self._hit_count = 0
        self._miss_count = 0
        
        logger.debug(f"📦 OHLCV Cache 초기화 (TTL: {default_ttl}초)")
    
    def _make_key(self, symbol: str, interval: str) -> str:
        """캐시 키 생성"""
        return f"{symbol}_{interval}"
    
    def get(
        self,
        symbol: str,
        interval: str = "minute60",
        count: int = 200,
        ttl: float = None
    ) -> Optional[Any]:
        """
        OHLCV 데이터 조회 (캐시 우선)
        
        Args:
            symbol: 마켓 심볼 (예: "KRW-BTC")
            interval: 시간 간격
            count: 캔들 개수
            ttl: 이 요청의 TTL (없으면 default_ttl 사용)
            
        Returns:
            pandas DataFrame 또는 None
        """
        key = self._make_key(symbol, interval)
        ttl = ttl or self.default_ttl
        
        # 캐시 확인
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                self._hit_count += 1
                logger.debug(f"📦 Cache HIT: {key}")
                return entry.data
            else:
                # 만료된 항목 삭제
                del self._cache[key]
        
        # 캐시 미스 - API 호출
        self._miss_count += 1
        logger.debug(f"📦 Cache MISS: {key}")
        
        try:
            data = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
            if data is not None and len(data) > 0:
                self._cache[key] = CacheEntry(
                    data=data,
                    timestamp=time.time(),
                    ttl=ttl
                )
                return data
            return None
        except Exception as e:
            logger.error(f"OHLCV 조회 실패 ({symbol}): {e}")
            return None
    
    def invalidate(self, symbol: str = None, interval: str = None):
        """
        캐시 무효화
        
        Args:
            symbol: 특정 심볼만 무효화 (없으면 전체)
            interval: 특정 인터벌만 무효화
        """
        if symbol is None:
            self._cache.clear()
            logger.debug("📦 Cache 전체 삭제")
        elif interval is None:
            # 해당 심볼의 모든 인터벌 삭제
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{symbol}_")]
            for key in keys_to_delete:
                del self._cache[key]
            logger.debug(f"📦 Cache 삭제: {symbol} (모든 인터벌)")
        else:
            key = self._make_key(symbol, interval)
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"📦 Cache 삭제: {key}")
    
    def get_stats(self) -> Dict:
        """캐시 통계 조회"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        
        return {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": hit_rate,
            "cached_items": len(self._cache)
        }
    
    def cleanup_expired(self):
        """만료된 캐시 항목 정리"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"📦 만료된 캐시 {len(expired_keys)}개 정리")


class RateLimiter:
    """
    API 호출 속도 제한기
    
    업비트 API 제한 (초당 10회) 준수를 위한 Rate Limiter.
    """
    
    def __init__(self, calls_per_second: int = 10):
        """
        Args:
            calls_per_second: 초당 최대 호출 수
        """
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self._last_call_time = 0.0
        self._call_count = 0
        
        logger.debug(f"⏱️ Rate Limiter 초기화 (초당 {calls_per_second}회)")
    
    def wait_if_needed(self):
        """
        필요시 대기
        
        마지막 호출 이후 충분한 시간이 지나지 않았으면 대기.
        """
        now = time.time()
        elapsed = now - self._last_call_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        
        self._last_call_time = time.time()
        self._call_count += 1
    
    def get_stats(self) -> Dict:
        """통계 조회"""
        return {
            "total_calls": self._call_count,
            "calls_per_second_limit": self.calls_per_second
        }


# 글로벌 인스턴스 (싱글톤 패턴)
_ohlcv_cache: Optional[OHLCVCache] = None
_rate_limiter: Optional[RateLimiter] = None


def get_ohlcv_cache(ttl: float = 60.0) -> OHLCVCache:
    """OHLCV 캐시 싱글톤 반환"""
    global _ohlcv_cache
    if _ohlcv_cache is None:
        _ohlcv_cache = OHLCVCache(default_ttl=ttl)
    return _ohlcv_cache


def get_rate_limiter(calls_per_second: int = 10) -> RateLimiter:
    """Rate Limiter 싱글톤 반환"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(calls_per_second=calls_per_second)
    return _rate_limiter


# Test
if __name__ == "__main__":
    print("=== Cache & Rate Limiter Test ===\n")
    
    cache = get_ohlcv_cache(ttl=30)
    limiter = get_rate_limiter(calls_per_second=5)
    
    # 캐시 테스트
    symbol = "KRW-BTC"
    
    print("1. 첫 번째 요청 (MISS 예상)...")
    limiter.wait_if_needed()
    data1 = cache.get(symbol, "minute60", count=5)
    print(f"   결과: {len(data1) if data1 is not None else 'None'}개 캔들")
    
    print("\n2. 두 번째 요청 (HIT 예상)...")
    data2 = cache.get(symbol, "minute60", count=5)
    print(f"   결과: {len(data2) if data2 is not None else 'None'}개 캔들")
    
    print(f"\n📊 캐시 통계: {cache.get_stats()}")
    print(f"⏱️ Rate Limiter 통계: {limiter.get_stats()}")
