"""Zilliz Cloud(Milvus) 기반 문서 청크 벡터 검색.

로컬 rag_index.sqlite3의 벡터를 코사인 유사도로 메모리에서 검색하던 방식(rag.py의
CompanyIndex) 대신, 일부 회사(MIGRATED_COMPANY_CODES)는 이 모듈을 통해 Zilliz Cloud에서
검색한다. 회사별 인덱스를 따로 두지 않고 컬렉션 하나에 company_code 메타데이터 필드를 두어,
Milvus 필터 표현식(`company_code in [...]`)으로 회사 필터링을 구현한다 — rag.py의
CODE_TO_COMPANY와 동일한 회사 코드를 그대로 쓴다.

migrated_company_codes에 없는 회사(DN오토모티브 등, 아직 Zilliz로 옮기지 않음)는 그대로
rag.py의 로컬 sqlite 인덱스를 계속 쓴다 — 이 모듈은 그 경로를 대체하지 않고 병행한다.

무료 티어(Zilliz Cloud Serverless) 한도: 벡터당 최대 768차원 · 컬렉션당 최대 100만 벡터.
현재 이관 대상(하나마이크론 + 벤치마킹 3사, scripts/migrate_to_zilliz.py 참고)은 28,000개로
한도 안에 여유 있게 들어간다.
"""
import os
from functools import lru_cache
from typing import Any, Optional

from pymilvus import DataType, MilvusClient

EMBED_DIM = 768
_TEXT_MAX_LEN = 65535  # Milvus VARCHAR 최대값. sqlite 기준 최장 텍스트는 7,211자였지만 Milvus의
# max_length는 UTF-8 바이트 기준이라(한글은 글자당 3바이트) 여유 없이 잡으면 넘칠 수 있어 상한을 그대로 쓴다.
_SHORT_MAX_LEN = 64

# 이 컬렉션으로 이미 옮긴 회사 코드 — rag.py가 검색 경로를 나누는 기준으로 그대로 가져다 쓴다.
MIGRATED_COMPANY_CODES = {"067310", "000660", "005930", "009150"}

COLLECTION_NAME = os.environ.get("ZILLIZ_COLLECTION", "esg_doc_chunks")

_OUTPUT_FIELDS = [
    "company_code",
    "company_name",
    "doc_id",
    "doc_type",
    "year",
    "page",
    "section_title",
    "content_type",
    "text",
]


@lru_cache
def get_client() -> MilvusClient:
    uri = os.environ.get("ZILLIZ_URI")
    token = os.environ.get("ZILLIZ_TOKEN")
    if not uri or not token:
        raise RuntimeError("ZILLIZ_URI / ZILLIZ_TOKEN이 설정되지 않았습니다 (backend/.env 확인).")
    return MilvusClient(uri=uri, token=token)


def ensure_collection() -> None:
    """컬렉션이 없으면 스키마 + 인덱스를 만들어 로드한다. 이미 있으면 아무것도 하지 않는다(멱등)."""
    client = get_client()
    if client.has_collection(COLLECTION_NAME):
        return

    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBED_DIM)
    schema.add_field("company_code", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("company_name", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("doc_type", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("year", DataType.INT64)
    schema.add_field("page", DataType.INT64)
    schema.add_field("section_title", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("content_type", DataType.VARCHAR, max_length=_SHORT_MAX_LEN)
    schema.add_field("text", DataType.VARCHAR, max_length=_TEXT_MAX_LEN)

    index_params = client.prepare_index_params()
    # 기존 로컬 검색(rag.py의 CompanyIndex)도 코사인 유사도를 썼으므로 동일하게 맞춘다 —
    # 점수 스케일이 같아야 두 경로의 결과를 answer_question에서 그대로 섞어 써도 어색하지 않다.
    index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")

    client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=index_params)


def upload_chunks(rows: list[dict[str, Any]], batch_size: int = 500) -> int:
    """rows(각 dict는 id/embedding/company_code/... 필드를 그대로 담고 있음)를 배치로 업로드한다."""
    client = get_client()
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.insert(collection_name=COLLECTION_NAME, data=batch)
        total += len(batch)
    return total


def count_rows(company_code: Optional[str] = None) -> int:
    """디버깅/검증용 — 컬렉션 전체 또는 특정 회사코드의 적재된 행 수."""
    client = get_client()
    filter_expr = f'company_code == "{company_code}"' if company_code else ""
    res = client.query(collection_name=COLLECTION_NAME, filter=filter_expr, output_fields=["count(*)"])
    return res[0]["count(*)"] if res else 0


def search_many(query_vecs: list[list[float]], company_codes: list[str], top_k: int = 8) -> list[dict[str, Any]]:
    """여러 쿼리 벡터 × company_code IN [...] 필터로 검색해 id 기준 최고점만 남기고 top_k를 반환한다.

    rag.py의 CompanyIndex.search_many와 동일한 반환 형태(dict 목록, score 포함)를 맞춰서
    호출부(_answer)가 로컬 경로와 이 경로를 구분 없이 다룰 수 있게 한다.
    """
    if not company_codes:
        return []
    client = get_client()
    codes_expr = ", ".join(f'"{c}"' for c in company_codes)
    filter_expr = f"company_code in [{codes_expr}]"

    best: dict[int, dict[str, Any]] = {}
    for qv in query_vecs:
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[qv],
            filter=filter_expr,
            limit=top_k,
            output_fields=_OUTPUT_FIELDS,
        )
        for hit in results[0] if results else []:
            rid = hit["id"]
            score = float(hit["distance"])  # COSINE metric — 클수록 더 유사
            if rid not in best or score > best[rid]["score"]:
                row = dict(hit["entity"])
                row["id"] = rid
                row["score"] = score
                best[rid] = row
    return sorted(best.values(), key=lambda r: -r["score"])[:top_k]
