"""
기존 hybrid_parse.py 결과(JSONL)에서 잡음 제거 — API 재호출 없이 로컬에서 정제
=====================================================================================
문제: LlamaParse가 사이드바 탭 라벨("ESG Performance", "Company Profile" 등),
러닝헤더(보고서 제목), 페이지번호를 본문과 이어붙여서 추출하는 경우가 있어,
그런 청크가 실제 본문보다 검색 순위에서 앞서는 문제 발견 (실제 하이브리드 검색
테스트에서 확인됨: "온실가스 배출량 저감 목표" 질의에 헤더 조각만 상위로 잡힘).

이 스크립트는 hybrid_parse.py를 다시 돌리지 않고(=LlamaParse 재호출 없이,
비용 발생 안 함), 이미 만들어진 JSONL 파일의 content 필드만 후처리로 정제합니다.
표(content_type="table")는 파이프(|)가 구조 문자라서 절대 건드리지 않습니다.

사용법:
    python clean_hybrid_chunks.py parsed_hybrid\000990_2025_sustainability_report.jsonl

    (같은 폴더에 *_cleaned.jsonl 로 저장 - 원본은 보존됨)
    확인 후 문제 없으면 원본을 교체:
    python clean_hybrid_chunks.py parsed_hybrid\000990_2025_sustainability_report.jsonl --overwrite
"""

import sys
import re
import json
from pathlib import Path

# hybrid_parse.py와 동일한 필터 (일관성 유지를 위해 그대로 복사)
MIN_CONTENT_LENGTH = 20
REPORT_TITLE_PATTERN = re.compile(r"\d{4}\s*-\s*\d{4}\s*DB\s*하이텍\s*ESG\s*경영\s*보고서")
PAGE_NUMBER_PATTERN = re.compile(r"-\s*\d{1,4}\s*-")
SIDEBAR_LABELS = [
    "Company Profile", "2023 At a Glance", "2024 At a Glance", "2025 At a Glance",
    "Sustainability", "ESG Performance", "Appendix",
]


def strip_boilerplate(text: str) -> str:
    cleaned = text
    cleaned = REPORT_TITLE_PATTERN.sub(" ", cleaned)
    for label in SIDEBAR_LABELS:
        cleaned = cleaned.replace(label, " ")
    cleaned = PAGE_NUMBER_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\*\*\s*\*\*", " ", cleaned)
    cleaned = re.sub(r"(?m)^\s*#+\s*$", "", cleaned)
    cleaned = re.sub(r"\s\|\s", " ", cleaned)
    cleaned = re.sub(r"(?m)^\s*\|+\s*$", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) < MIN_CONTENT_LENGTH:
        return ""
    return cleaned


def clean_jsonl(in_path: Path, overwrite: bool):
    rows = []
    n_total = 0
    n_dropped = 0
    n_cleaned = 0

    with open(in_path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            n_total += 1

            if row.get("content_type") == "table":
                rows.append(row)  # 표는 절대 건드리지 않음
                continue

            original = row["content"]
            cleaned = strip_boilerplate(original)

            if not cleaned:
                n_dropped += 1
                continue  # 잡음만 남은 청크는 버림

            if cleaned != original:
                n_cleaned += 1
                row["content"] = cleaned
                row["chunk_char_count"] = len(cleaned)

            rows.append(row)

    # chunk_id 재채번 (버려진 청크가 있어 번호가 비므로)
    doc_id = rows[0]["doc_id"] if rows else ""
    for idx, row in enumerate(rows):
        row["chunk_id"] = f"{doc_id}_{idx:04d}"

    out_path = in_path if overwrite else in_path.with_name(in_path.stem + "_cleaned.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"원본 청크 수     : {n_total}")
    print(f"내용 정제된 청크 : {n_cleaned}")
    print(f"잡음으로 버려진 청크: {n_dropped}")
    print(f"최종 청크 수     : {len(rows)}")
    print(f"저장 위치        : {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    in_path = Path(sys.argv[1])
    overwrite = "--overwrite" in sys.argv

    if not in_path.exists():
        sys.exit(f"파일을 찾을 수 없습니다: {in_path}")

    clean_jsonl(in_path, overwrite)
