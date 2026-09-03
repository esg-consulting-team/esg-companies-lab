"""
S(사회) need_review 항목 검수용 워크북 생성
=====================================================================
rag_layer_S.py가 생성한 채점 결과(S_채점결과_000990.csv)에서 need_review=True인
항목만 뽑아, 팀원이 원문 근거를 눈으로 확인하고 바로 수기 보완할 수 있도록
정리한 xlsx를 만든다. 팀이 이미 쓰고 있는 ESG_핵심지표_채점기준표_S(사회).xlsx의
컬럼 이름([입력]충족단계/요건수, 자사취득점수, 비고)을 그대로 따라서, 검수 후
값을 원본 워크북에 바로 옮겨 적기 쉽게 했다.

사용법:
    python build_S_review_sheet.py --company-code 000990 --company-name DB하이텍 ^
        --scored-csv S_채점결과_000990.csv --persist-dir "C:/hewon/esg-workspace/chroma_db" ^
        --out S_검수필요_000990.xlsx
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import rag_layer_S as s

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Border(*(Side(style="thin", color="D9D9D9"),) * 4)


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def build_summary_sheet(wb, nr: pd.DataFrame):
    ws = wb.active
    ws.title = "1_검수필요_요약"
    cols = [
        ("분류코드", 12), ("항목명", 22), ("채점유형", 10), ("RAG 산정 점수", 12),
        ("confidence", 10), ("RAG 판단 근거", 55), ("근거_chunk_id", 30),
        ("[검수]확인결과", 16), ("[검수]수정점수", 12), ("[검수]비고", 30),
    ]
    ws.append([c for c, _ in cols])
    for i, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    _style_header(ws)

    for _, r in nr.iterrows():
        ws.append([
            r["분류코드"], r["항목명"], r["채점유형"], r["자사취득점수"], r["confidence"],
            r["rationale"], r["근거_chunk_ids"], "", "", "",
        ])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP
            cell.border = THIN
    ws.freeze_panes = "A2"


def build_evidence_sheet(wb, nr: pd.DataFrame, chunk_map: dict):
    ws = wb.create_sheet("2_검수필요_근거원문")
    cols = [
        ("분류코드", 12), ("항목명", 22), ("chunk_id", 30), ("문서종류", 16),
        ("페이지", 8), ("섹션", 18), ("유형", 8), ("원문", 90),
    ]
    ws.append([c for c, _ in cols])
    for i, (_, w) in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    _style_header(ws)

    for _, r in nr.iterrows():
        ids = [x for x in str(r["근거_chunk_ids"]).split(";") if x and x != "nan"]
        if not ids:
            ws.append([r["분류코드"], r["항목명"], "(근거 청크 없음)", "", "", "", "", ""])
            continue
        for cid in ids:
            c = chunk_map.get(cid, {})
            ws.append([
                r["분류코드"], r["항목명"], cid, c.get("doc_type", ""),
                c.get("page", ""), c.get("section_title", ""), c.get("content_type", ""),
                c.get("content", "(청크를 찾지 못함)"),
            ])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP
            cell.border = THIN
    ws.freeze_panes = "A2"


def build_readme_sheet(wb, company_code, company_name, n_total, n_review):
    from datetime import datetime, timezone
    ws = wb.create_sheet("0_안내", 0)
    ws.column_dimensions["A"].width = 100
    lines = [
        f"S(사회) RAG 자동채점 검수 요청 — {company_name}({company_code})",
        "",
        f"생성 시각: {datetime.now(timezone.utc).isoformat()}",
        f"전체 {n_total}개 항목 중 need_review 플래그 {n_review}건",
        "",
        "확인 방법:",
        "1) '1_검수필요_요약' 시트에서 항목별 RAG 판단 근거(rationale)를 먼저 읽는다.",
        "2) 근거가 부족하다고 판단된 이유를 '2_검수필요_근거원문' 시트에서 실제 보고서",
        "   원문(청크)으로 대조 확인한다 — chunk_id로 두 시트가 서로 연결된다.",
        "3) 원문에서 실제 값을 확인했으면 '1_검수필요_요약' 시트의 [검수]확인결과/",
        "   [검수]수정점수/[검수]비고 칸에 채워 넣는다.",
        "4) 최종 확정값은 ESG_핵심지표_채점기준표_S(사회).xlsx의 01시트",
        "   [입력]충족단계/요건수 · 자사취득점수 · 비고 칸에 옮겨 적는다.",
        "",
        "주의: need_review로 표시되지 않은 나머지 항목도 RAG가 자동 산정한 값이므로",
        "표본 확인 차원에서 몇 개는 원문 대조를 권장함 (전량 신뢰 금지).",
    ]
    for i, line in enumerate(lines, start=1):
        cell = ws.cell(i, 1, line)
        if i == 1:
            cell.font = Font(bold=True, size=13)
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-code", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--scored-csv", required=True)
    parser.add_argument("--persist-dir", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = "dummy-not-called"  # get()은 임베딩 호출 없이 동작

    df = pd.read_csv(args.scored_csv, encoding="utf-8-sig")
    nr = df[df["need_review"] == True].copy()
    if nr.empty:
        sys.exit("need_review 항목이 없습니다 — 검수 시트를 만들 필요가 없습니다.")

    vectorstore, _ = s.load_existing_index(args.persist_dir)
    all_ids = set()
    for ids_str in nr["근거_chunk_ids"].dropna():
        all_ids.update(x for x in str(ids_str).split(";") if x and x != "nan")

    chunk_map = {}
    if all_ids:
        raw = vectorstore.get(ids=list(all_ids), include=["documents", "metadatas"])
        for cid, doc, meta in zip(raw["ids"], raw["documents"], raw["metadatas"]):
            chunk_map[cid] = {
                "content": doc, "doc_type": meta.get("doc_type"), "page": meta.get("page"),
                "section_title": meta.get("section_title"), "content_type": meta.get("content_type"),
            }

    wb = Workbook()
    build_summary_sheet(wb, nr)
    build_evidence_sheet(wb, nr, chunk_map)
    build_readme_sheet(wb, args.company_code, args.company_name, len(df), len(nr))

    out_path = args.out or f"S_검수필요_{args.company_code}.xlsx"
    wb.save(out_path)
    print(f"저장 완료: {out_path} ({len(nr)}개 항목, 근거 청크 {len(chunk_map)}개)")


if __name__ == "__main__":
    main()
