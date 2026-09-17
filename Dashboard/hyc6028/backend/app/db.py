import threading

from supabase import Client, create_client

from app.config import get_settings

_local = threading.local()


def get_supabase() -> Client:
    """스레드별로 클라이언트를 캐시해서 재사용한다.

    postgrest-py는 내부 httpx 클라이언트를 http2=True로 고정하는데, 여러 FastAPI
    스레드가 클라이언트 하나를 '동시에' 공유하면 멀티플렉싱 스트림 처리 문제로
    'Server disconnected' 오류가 난다 (겪었던 버그). 반대로 매 호출마다 새
    클라이언트를 만들면 매번 TLS 핸드셰이크 비용을 치러서, 한 요청 안에서 여러
    번 조회하는 요즘 서비스 함수들(요약/항목상세 등)이 심하게 느려진다(10초+).

    thread-local로 캐시하면: 같은 스레드 안에서는 어차피 호출이 순차적이라
    커넥션을 재사용해도 안전하고, 서로 다른 요청이 서로 다른 스레드에서
    처리되는 한 클라이언트 객체 자체를 공유하지 않으므로 동시성 버그도
    재발하지 않는다.
    """
    client = getattr(_local, "client", None)
    if client is None:
        settings = get_settings()
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        _local.client = client
    return client
