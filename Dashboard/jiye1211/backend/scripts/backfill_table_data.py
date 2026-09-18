# -*- coding: utf-8 -*-
"""rag_index.sqlite3에 table_data(표 원본 JSON) 컬럼을 추가하고 원본 chroma DB에서 채워 넣는다.

content_type='table'인 청크는 원래 텍스트가 마크다운 파이프 표라 그대로 보여주면 지저분하다.
원본 chroma_db_migrated에는 같은 청크에 대해 이미 파싱된 표(행 배열의 JSON)가 `table_data`
메타데이터로 남아 있으므로, id로 조인해서 그대로 가져온다 (재임베딩 불필요).

실행: backend 디렉터리에서
    .venv\\Scripts\\python.exe scripts\\backfill_table_data.py
"""
import sqlite3
from pathlib import Path

SOURCE_DB = r"D:\ESG\db\chroma_db_migrated\chroma.sqlite3"
TARGET_DB = str(Path(__file__).resolve().parent.parent / "data" / "rag_index.sqlite3")


def main() -> None:
    target = sqlite3.connect(TARGET_DB)
    cols = [r[1] for r in target.execute("PRAGMA table_info(chunks)").fetchall()]
    if "table_data" not in cols:
        target.execute("ALTER TABLE chunks ADD COLUMN table_data TEXT")
        target.commit()
        print("[backfill_table_data] table_data 컬럼 추가")

    ids = [r[0] for r in target.execute("SELECT id FROM chunks WHERE content_type='table'").fetchall()]
    print(f"[backfill_table_data] 대상(표) 청크 수: {len(ids)}")
    if not ids:
        target.close()
        return

    src = sqlite3.connect(SOURCE_DB)
    placeholders = ",".join("?" for _ in ids)
    cur = src.execute(
        f"SELECT id, string_value FROM embedding_metadata WHERE key='table_data' AND id IN ({placeholders})",
        ids,
    )
    updated = 0
    with target:
        for _id, table_json in cur:
            if not table_json:
                continue
            target.execute("UPDATE chunks SET table_data = ? WHERE id = ?", (table_json, _id))
            updated += 1
    src.close()
    target.close()
    print(f"[backfill_table_data] 반영: {updated}건")


if __name__ == "__main__":
    main()
