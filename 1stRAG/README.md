# 1stRAG — ESG 채점 RAG 파이프라인 스냅샷 (2026-09-04)

`esg-rag-scoring` 저장소에서 팀 프로젝트 방향성을 이해하는 데 필요한 핵심 파일만 옮겨왔습니다.
(원본: `raw_pdf/`, `parsed_hybrid/`, `chroma_db/`, `.env` 등 대용량/생성 데이터·시크릿은 제외)

## 지금 상태 요약

- **파일럿 대상**: SK하이닉스(000660), 91개 K-ESG 항목 전체 채점
- **실제 채점 모델**: `score__model/2하이닉스_v2.1_Stage4 full91 shared index.ipynb`
  (⚠️ 같은 폴더의 `ESG_Scoring_hybrid_v7/v8_SKHY.ipynb`, 저장소의 `rag_layer_S.py`는 **사용하지 않는 이전 버전**이라 이 스냅샷에서 제외했습니다)
- **260903 회의**: Plumber 단독 인덱싱 모델 채택, 근거 표기 형식(`[문서명] p.페이지. 문장(줄번호)`) 확정
- **260904 회의**: 외부 의사결정자 검토 결과 아키텍처 전환 결정 — Full RAG(매 요청마다 벡터 검색) → 배치 ETL + 정형DB 이원화로 전환. 14~15일 오프라인 검수 예정

## 이번 세션에서 발견·수정한 버그 (실제 모델 코드 기준)

최호연·김민주님의 91문항 수기 검수(21건 플래그)를 코드에서 재현·수정:

1. **출처 문서 혼동** — `locate_citation()`이 LLM 인용 문구와 실제 근거 텍스트 매칭에 실패하면 검색 1순위 청크로 임의 귀속시키던 버그. 근거 1건일 때만 귀속하고, 여러 건이면 "자동 특정 실패"로 표시 + 검토 플래그.
2. **복합가중형 단순 평균** — 세부요소 간 가중치 없이 균등 평균하던 것을 LLM이 답하는 가중치 기반 가중평균으로 변경 (G-3-3이 4개년 내내 1.3점에 고정되던 현상과 일치, 근거 파일: `000660_train/*.xlsx`).
3. **근거충분성 미반영** — LLM이 "근거충분성: 불충분"이라 스스로 답해도 검토 플래그로 연결되지 않던 것을 수정.
4. `llamaparse_rescue.ipynb` — 재처리 결과 개수가 요청과 다르면 경고만 찍고 진행하던 것을 예외 처리로 변경(잘못된 페이지 번호가 인덱스에 고정되는 것 방지).
5. `docs/채점기준표/ESG_핵심지표_채점기준표_전체_v2.xlsx` — G-2-4 실사진단질문 오기재 수정, "추세"(CAGR 기준)·"원단위" 용어 정의 추가.

**자세한 근거·코드 스니펫**: 아래 두 문서 참고 (Claude Artifact, 비공개 — 팀 공유 필요 시 링크 소유자가 공유 설정 변경 필요)
- [출처 매핑·채점 로직 버그 진단 리포트](https://claude.ai/code/artifact/dacdae03-41e3-4be1-965d-5bbecf1aa71b)
- [정형DB 전환 로드맵 (WBS 개정안)](https://claude.ai/code/artifact/43bafa48-5e54-4dbf-a42e-37aec7e06290)

## 폴더 구성

```
docs/
  ESG_project_WBS_v1.0.xlsx        # 프로젝트 WBS (8/18~9/23)
  등급표/KCGS_평가등급_2022-2025.xlsx
  채점기준표/ESG_핵심지표_채점기준표_전체_v2.xlsx   # 91항목 채점기준표 (오늘 수정본)
  회의록/                           # 260903·260904 회의록, RAG 설계 배경, 파싱 모델 비교
score__model/
  2하이닉스_v2.1_Stage4 full91 shared index.ipynb   # 실제 채점 모델 (수정 완료)
  esg_query_interface.ipynb        # 공용 조회 인터페이스 (get_evidence 등)
  llamaparse_rescue.ipynb          # 인덱스 재처리 (수정 완료)
  build_rag_index_v6_production.ipynb  # 공용 Chroma 인덱스 구축
  RAG_DB_incident_and_version_log.md   # 인덱싱 파이프라인 버전 히스토리·장애 기록
  채점 모델 검수 (최호연 김민주).xlsx      # 91문항 수기 검수 결과
joint_layer/                       # 인덱싱/파싱 관련 팀원별 실험 노트북
000660_train/                      # SK하이닉스 4개년(2022~2025) 채점 완료 결과
requirements.txt
```
