from supabase import Client, create_client

from app.config import get_settings


def get_supabase() -> Client:
    """새 클라이언트를 매 호출마다 생성한다.

    postgrest-py는 내부 httpx 클라이언트를 http2=True로 고정하는데, 여러
    FastAPI 스레드가 캐시된 클라이언트 하나를 동시에 공유하면 멀티플렉싱
    스트림 처리 문제로 'Server disconnected' 오류가 발생한다. 요청마다
    새 클라이언트를 만들어 스레드 간 연결 공유를 피한다.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)
