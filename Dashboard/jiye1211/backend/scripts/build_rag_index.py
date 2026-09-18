# -*- coding: utf-8 -*-
"""db/chroma_db_migrated의 원문 청크를 다시 임베딩해 backend/data/rag_index.sqlite3로 옮긴다.

원본 chroma_db_migrated는 HNSW 벡터 인덱스(실제 float 벡터)가 마이그레이션 과정에서 유실되어
그대로는 유사도 검색을 할 수 없다 (원문 텍스트·메타데이터는 sqlite에 온전히 남아 있음).
그래서 대상 회사(DN오토모티브 007340 · 하나마이크론 067310)의 청크만 골라 Gemini
임베딩(gemini-embedding-001, 768차원)으로 다시 벡터화한다. 재실행해도 이미 처리한 id는 건너뛴다.

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

SOURCE_DB = r"D:\ESG\db\chroma_db_migrated\chroma.sqlite3"
TARGET_DB = str(Path(__file__).resolve().parent.parent / "data" / "rag_index.sqlite3")
COMPANY_CODES = ["007340", "067310"]  # DN오토모티브, 하나마이크론
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
