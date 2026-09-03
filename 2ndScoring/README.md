# 2ndScoring — ESG 자체 채점체계 (Phase 2)

WBS 기준 "2. ESG 자체 채점체계 구축" ~ "3. 점수산출모델 실행" 단계 산출물.
담당: 진혜원 (전체 채점 모델 / 채점기준표 정비 / SK하이닉스 000660 모범 데이터셋).

전체 개발 히스토리와 실행 로그가 포함된 원본 작업 저장소는
[hewonjin/esg-rag-scoring](https://github.com/hewonjin/esg-rag-scoring) 참고.
여기에는 그중 산출물의 근거가 되는 파일만 정리해서 옮겼습니다
(Chroma 벡터 DB(.sqlite3, 2GB+)는 용량상 제외 — 재현하려면 원본 저장소의
`joint_layer/build_rag_index_v6_production.ipynb`로 재인덱싱).

## 구성

- `docs/채점기준표/` — K-ESG v2.0 기반 91개 항목 채점기준표(전체/E/S/G+P). `01_ESG통합진단마스터`
  시트의 `자사취득점수(0~100)` 계산식은 데이터팀 피드백(0점이 "미채점"과 혼동됨)을 반영해
  최하위 단계도 1점 이상이 되도록 수정함(`MAX(1, ...)`).
- `docs/` 기타 — 기획서, WBS, KCGS 평가등급표, S(사회) 채점기준표 사본.
- `score__model/` — 전체 채점 모델 본체(`ESG_Scoring_hybrid_v8_SKHY.ipynb`, 하이브리드 RAG
  검색 + Gemini 판단 + Python 산술), 쿼리 인터페이스, LlamaParse 보완 노트북, 파싱 모델별
  (pdfplumber vs LlamaParse) 채점 성능 비교 문서.
- `individual_layer/` — S(사회) 개별 레이어 RAG 채점 스크립트 및 검수 시트.
- `joint_layer/` — 인덱싱(임베딩/청킹/하이브리드 검색) 파이프라인 v4~v6, 팀원별 실험 노트북.
- `000660_train/` — 1호 모범 트레인 데이터셋: SK하이닉스(000660) 2022~2025 4개년 전체 채점
  완료본. 비고란에 근거페이지/원문 인용/근거충분성(충분·부분적·불충분) 판단을 모두 명시.

## 모델

전 구간 `gemini-3.1-flash-lite`로 통일 (임베딩은 `gemini-embedding-001` 별도 유지).
