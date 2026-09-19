# -*- coding: utf-8 -*-
"""backend/data/rag_index.sqlite3에 이미 있는 벡터(재임베딩 없음)를 Zilliz Cloud(Milvus)
컬렉션으로 업로드한다 — 새로 임베딩하지 않고 기존 벡터를 그대로 옮기는 1회성 이관 스크립트다.

대상은 하나마이크론 + 그 벤치마킹 3사(SK하이닉스·삼성전자·삼성전기, app/milvus_client.py
MIGRATED_COMPANY_CODES와 반드시 같아야 한다)뿐이다 — DN오토모티브 등 나머지 회사는 이번에
옮기지 않고 계속 로컬 sqlite 인덱스(rag.py의 CompanyIndex)로 검색한다.

업로드 전 Zilliz Cloud Serverless 무료 티어 한도(벡터당 최대 768차원 · 컬렉션당 최대 100만
벡터)를 실제로 확인하고, 벗어나면 업로드를 시작하지 않고 중단한다.

실행: backend 디렉터리에서
    .venv\\Scripts\\python.exe scripts\\migrate_to_zilliz.py
"""
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app import milvus_client  # noqa: E402

SOURCE_DB = str(Path(__file__).resolve().parent.parent / "data" / "rag_index.sqlite3")
FREE_TIER_MAX_DIM = 768
FREE_TIER_MAX_VECTORS = 1_000_000


def fetch_target_rows(con: sqlite3.Connection) -> list[dict]:
    codes = tuple(sorted(milvus_client.MIGRATED_COMPANY_CODES))
    placeholders = ",".join("?" for _ in codes)
    cur = con.execute(
        f"""
        SELECT id, company_code, company_name, doc_id, doc_type, year, page,
               section_title, content_type, text, embedding
        FROM chunks
        WHERE company_code IN ({placeholders})
        ORDER BY id
        """,
        codes,
    )
    cols = [d[0] for d in cur.description]
    rows = []
    for r in cur:
        row = dict(zip(cols, r))
        vec = np.frombuffer(row.pop("embedding"), dtype=np.float32)
        if vec.shape[0] != FREE_TIER_MAX_DIM:
            raise RuntimeError(f"id={row['id']} 벡터 차원이 {vec.shape[0]}입니다(768이어야 함) — 중단.")
        row["embedding"] = vec.tolist()
        rows.append(row)
    return rows


def main() -> None:
    con = sqlite3.connect(SOURCE_DB)
    try:
        rows = fetch_target_rows(con)
    finally:
        con.close()

    print(f"이관 대상: {len(rows)}개 청크 (회사코드 {sorted(milvus_client.MIGRATED_COMPANY_CODES)})")

    # ── 무료 티어 한도 확인(업로드 시작 전) ──────────────────────────────
    if len(rows) == 0:
        print("이관할 행이 없습니다 — 중단.")
        return
    if len(rows) > FREE_TIER_MAX_VECTORS:
        print(f"[중단] 대상 벡터 수({len(rows)})가 무료 티어 한도({FREE_TIER_MAX_VECTORS})를 초과합니다.")
        return
    print(f"한도 확인 완료 — 차원 768 이하(실측 768) · 벡터 수 {len(rows)} ≤ {FREE_TIER_MAX_VECTORS}")

    milvus_client.ensure_collection()

    t0 = time.time()
    uploaded = milvus_client.upload_chunks(rows, batch_size=500)
    elapsed = time.time() - t0
    print(f"업로드 완료: {uploaded}개, {elapsed:.1f}초")

    # ── 검증: 회사별 sqlite 원본 개수 vs Zilliz 적재 개수 비교 ───────────
    by_company: dict[str, int] = {}
    for r in rows:
        by_company[r["company_code"]] = by_company.get(r["company_code"], 0) + 1

    print("\n검증 (sqlite 원본 개수 vs Zilliz 적재 개수):")
    all_match = True
    for code, expected in sorted(by_company.items()):
        actual = milvus_client.count_rows(code)
        ok = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_match = False
        print(f"  {code}: sqlite {expected} / zilliz {actual}  [{ok}]")

    total_actual = milvus_client.count_rows()
    print(f"\n전체: sqlite {len(rows)} / zilliz {total_actual}  [{'OK' if all_match and total_actual == len(rows) else 'MISMATCH'}]")


if __name__ == "__main__":
    main()
