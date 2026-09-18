"""공용 TTL 캐시 유틸 — repository.py/roadmap.py/company_profile.py의 정적 참조 데이터 조회
함수에 붙이는 @lru_cache를 TTL 있는 캐시로 교체하기 위한 헬퍼.

Supabase에서 읽어온 값(기업코드, esg_company_id, esg_diagnosis 행 등)을 프로세스 메모리에
기본 5분간만 들고 있다가 자동 만료시킨다. lru_cache와 달리 Supabase 데이터를 개발 중 직접
고쳤을 때 서버를 재시작하지 않아도 최대 5분 후 자동으로 반영되고, POST /api/admin/clear-cache
로 즉시 비울 수도 있다(main.py 참고).
"""
import threading
from typing import Any, Callable, TypeVar

from cachetools import TTLCache, cached

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_TTL_SECONDS = 300  # 5분

_registered_caches: list[TTLCache] = []


def ttl_cache(ttl: float = DEFAULT_TTL_SECONDS, maxsize: int = 128) -> Callable[[F], F]:
    """functools.lru_cache 자리를 그대로 대체하는 TTL 버전 데코레이터.

    FastAPI가 동기(def) 라우트를 스레드풀에서 돌리기 때문에, cachetools 문서 권장대로
    lock을 넘겨 스레드 안전하게 만든다(functools.lru_cache는 내부적으로 이미 스레드 안전).
    """
    cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
    _registered_caches.append(cache)
    lock = threading.RLock()
    return cached(cache=cache, lock=lock)


def clear_all_caches() -> int:
    """등록된 모든 TTL 캐시를 즉시 비운다. 반환값은 비우기 직전 총 항목 수(확인용)."""
    total = 0
    for cache in _registered_caches:
        total += len(cache)
        cache.clear()
    return total
