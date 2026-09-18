# -*- coding: utf-8 -*-
"""db/chroma_db_migrated의 원문 청크를 다시 임베딩해 backend/data/rag_index.sqlite3로 옮긴다.

Gemini API로 다시 임베딩하는 이유(중요 — 과거 진단을 실측으로 바로잡음):
애초 "원본 chroma_db_migrated는 HNSW 벡터 인덱스가 마이그레이션 과정에서 유실됐다"고 봤으나
이는 틀렸다 — chromadb.PersistentClient로 직접 열어 자기-유사도 쿼리(distance=0.0)까지
확인했고, 원본 벡터가 gemini-embedding-001의 네이티브 3072차원 출력이며 앞 768개만 잘라
재정규화하면 API에 output_dimensionality=768로 직접 요청한 값과 코사인 유사도
0.9999999999999999(사실상 동일)임도 실측으로 확인했다. 즉 원본 벡터를 재사용하는 것이
수학적으로는 완전히 타당하다.

다만 실제로 재사용을 시도해보니, 이 legacy 포맷 인덱스를 훨씬 최신 버전인 chromadb(1.5.9,
Rust 코어)로 열어 `collection.get(..., include=["embeddings"])`를 반복 호출하면 같은 id로도
"Error loading hnsw index"가 간헐적으로(때로는 성공, 때로는 연속 실패) 발생했다 — 버전 불일치나
백그라운드 compactor/backfill 프로세스와의 경합으로 추정된다. db/chroma_db_migrated는 git에
커밋돼 있지 않아 복구 수단이 없으므로, 원인을 더 파고들며 반복 접근해 원본을 불안정하게
만들기보다 이미 안정적으로 검증된 Gemini API 재임베딩으로 되돌렸다(참고로 Gemini 텍스트
임베딩은 무료라 API를 다시 타는 것 자체의 비용 문제는 없다). 재실행해도 이미 처리한 id는
건너뛴다.

COMPANY_CODES는 자사 2곳(DN오토모티브·하나마이크론)에 app/benchmark_config.BENCHMARK_MAP의
벤치마킹 대상 회사 7곳을 더한 목록이다 — 챗봇이 "벤치마킹사는 어떻게 하고 있어?" 같은 질문에서
벤치마킹 대상 회사의 문서까지 검색하려면(rag._resolve_doc_search_companies) 그 회사들도 여기
포함돼 임베딩까지 끝나 있어야 한다.

실행: backend 디렉터리에서
    .venv\\Scripts\\python.exe scripts\\build_rag_index.py
"""
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.gemini_client import embed_texts  # noqa: E402

SOURCE_DB = str(Path(__file__).resolve().parents[2] / "db" / "chroma_db_migrated" / "chroma.sqlite3")
TARGET_DB = str(Path(__file__).resolve().parent.parent / "data" / "rag_index.sqlite3")
COMPANY_CODES = [
    "007340",  # DN오토모티브
    "067310",  # 하나마이크론
    "267260",  # HD현대일렉트릭 (DN오토모티브 벤치마킹)
    "010120",  # 엘에스일렉트릭 (DN오토모티브 벤치마킹)
    "361610",  # SK아이이테크놀로지 (DN오토모티브 벤치마킹)
    "001440",  # 대한전선 (DN오토모티브 벤치마킹)
    "009150",  # 삼성전기 (하나마이크론 벤치마킹)
    "000660",  # SK하이닉스 (하나마이크론 벤치마킹)
    "005930",  # 삼성전자 (하나마이크론 벤치마킹)
]
BATCH_SIZE = 80
EMBED_DIM = 768


def ensure_target_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            company_code TEXT,
            company_name TEXT,
            doc_id TEXT,
            doc_type TEXT,
            year INTEGER,
            page INTEGER,
            section_title TEXT,
            content_type TEXT,
            chunk_char_count INTEGER,
            text TEXT,
            embedding BLOB
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_chunks_company ON chunks(company_code)")
    con.commit()


def fetch_target_ids(company_codes: list[str]) -> list[int]:
    src = sqlite3.connect(SOURCE_DB)
    cur = src.cursor()
    placeholders = ",".join("?" for _ in company_codes)
    cur.execute(
        f"SELECT id FROM embedding_metadata WHERE key='company_code' AND string_value IN ({placeholders})",
        company_codes,
    )
    ids = [r[0] for r in cur.fetchall()]
    src.close()
    return ids


def fetch_rows(ids: list[int]) -> list[dict]:
    src = sqlite3.connect(SOURCE_DB)
    cur = src.cursor()
    placeholders = ",".join("?" for _ in ids)
    cur.execute(f"SELECT id, key, string_value, int_value FROM embedding_metadata WHERE id IN ({placeholders})", ids)
    rows: dict[int, dict] = {i: {"id": i} for i in ids}
    for _id, key, sv, iv in cur.fetchall():
        rows[_id][key] = sv if sv is not None else iv
    src.close()

    out = []
    for _id, d in rows.items():
        out.append(
            {
                "id": _id,
                "company_code": d.get("company_code"),
                "company_name": d.get("company_name"),
                "doc_id": d.get("doc_id"),
                "doc_type": d.get("doc_type"),
                "year": d.get("year"),
                "page": d.get("page"),
                "section_title": d.get("section_title"),
                "content_type": d.get("content_type"),
                "chunk_char_count": d.get("chunk_char_count"),
                "text": d.get("chroma:document") or "",
            }
        )
    return out


def main() -> None:
    target = sqlite3.connect(TARGET_DB)
    ensure_target_schema(target)

    all_ids = fetch_target_ids(COMPANY_CODES)
    print(f"[build_rag_index] 대상 청크 수: {len(all_ids)}")

    existing = {r[0] for r in target.execute("SELECT id FROM chunks").fetchall()}
    todo_ids = [i for i in all_ids if i not in existing]
    print(f"[build_rag_index] 이미 처리됨: {len(existing)}  /  남은 작업: {len(todo_ids)}")

    done = 0
    for i in range(0, len(todo_ids), BATCH_SIZE):
        batch_ids = todo_ids[i : i + BATCH_SIZE]
        rows = fetch_rows(batch_ids)
        # id 순서를 rows와 일치시켜 임베딩 결과와 정확히 매칭
        texts = [r["text"][:8000] if r["text"] else " " for r in rows]

        attempt = 0
        while True:
            try:
                vectors = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", output_dimensionality=EMBED_DIM)
                break
            except Exception as e:  # noqa: BLE001
                attempt += 1
                if attempt > 5:
                    raise
                wait = min(30, 2**attempt)
                print(f"  [경고] 임베딩 실패({e}), {wait}s 후 재시도 ({attempt}/5)")
                time.sleep(wait)

        with target:
            for row, vec in zip(rows, vectors):
                arr = np.asarray(vec, dtype=np.float32)
                target.execute(
                    """
                    INSERT OR REPLACE INTO chunks
                    (id, company_code, company_name, doc_id, doc_type, year, page,
                     section_title, content_type, chunk_char_count, text, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["company_code"],
                        row["company_name"],
                        row["doc_id"],
                        row["doc_type"],
                        row["year"],
                        row["page"],
                        row["section_title"],
                        row["content_type"],
                        row["chunk_char_count"],
                        row["text"],
                        arr.tobytes(),
                    ),
                )

        done += len(batch_ids)
        print(f"  진행: {done}/{len(todo_ids)}")

    target.close()
    print("[build_rag_index] 완료.")


if __name__ == "__main__":
    main()
