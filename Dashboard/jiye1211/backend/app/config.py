"""환경설정 로딩."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_embedding_model: str = os.environ.get("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
    gemini_chat_model: str = os.environ.get("GEMINI_CHAT_MODEL", "models/gemini-3.6-flash")
    rag_db_path: str = os.environ.get("RAG_DB_PATH", "./data/rag_index.sqlite3")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_ANON_KEY가 설정되지 않았습니다. "
            "backend/.env 파일을 확인하세요 (.env.example 참고)."
        )
    return settings
