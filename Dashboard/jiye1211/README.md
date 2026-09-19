# ESG 통합 진단 센터

`db/ESG_대시보드_전체화면_사양서_v2.md` 사양서를 바탕으로, Supabase에 적재된 실제 진단 데이터(`esg_diagnosis`
테이블 — DN오토모티브 · 하나마이크론, 각 42개 항목)로 동작하는 웹 앱입니다.

- **Backend**: Python + FastAPI (`backend/`) — Supabase에서 읽어 화면용 JSON으로 가공
- **Frontend**: React + TypeScript + Vite (`frontend/`) — 사양서 §13 디자인 시스템(다크 단일 테마 · KCGS 팔레트) 그대로 구현

## 구현 범위

사양서가 정의하는 L1~L7 7개 화면을 **모두 구현**했습니다.

- **L1 종합 현황 · L2 영역별 진단 · L3 항목 상세**: `esg_diagnosis` 실데이터 기반 (아래 표 참고).
- **L4 비교 분석**: 컨설팅 보고서(docx)에서 사람이 직접 검증해 만든 `db/report_extracted_data.json`
  (그룹비교·선례·KCGS 상관도)과, `esg_companies`/`company_esg_yearly` + `backend/app/benchmark_config.py`의
  벤치마킹사 매핑을 조합한 "자사 vs 벤치마킹군" Exhibit.
- **L5 개선 로드맵**: `esg_roadmap_stages` / `esg_roadmap_tasks` / `esg_urgency_criteria` /
  `esg_disclosure_deadline`(Supabase, 컨설팅 보고서 §08 로드맵 원문을 그대로 옮긴 테이블) 기반 4단계
  실행 로드맵.
- **L6 증빙 데이터룸**: `esg_diagnosis`의 채점 근거 텍스트에서 키워드로 추출한 참고자료 유형별 연결
  항목 수(근사치)와, 근거충분성이 낮은 항목 목록.
- **L7 리포트**: `esg_company_profile`(Supabase) 원본 필드를 가공 없이 그대로 보여주는 표지.

L4~L7은 레일 메뉴에서 모두 활성화되어 있습니다.

### 실제 데이터 vs 샘플 데이터

| 구분 | 소스 | 비고 |
|---|---|---|
| 항목별 점수·시급성·해결방안·채점근거 | Supabase `esg_diagnosis` (실데이터) | 42개 항목 × 2개사 |
| 근거충분성(충분/부분/불충분) | `note_scoring_model_25` 컬럼에서 정규식 파싱 | 84행 중 77행 매칭, 7행은 "평가 예정" |
| 판단근거/확인근거/감점사유, 해결방안 3분할 | `note_manual_ai_scoring_26` / `solution` 컬럼 파싱 | DN오토모티브는 대체로 구조화된 마커를 사용해 잘 파싱됨. 하나마이크론은 자유서술이 많아 파싱 실패 시 원문 그대로 표시 |
| L3 "출처: 문서명 p.페이지" 캡션 | `note_scoring_model_25` / `note_manual_ai_scoring_26` 파싱 (`extract_evidence_sources`) | 전체 84행 중 77행(91.7%) 매칭, 나머지는 캡션 자체를 렌더링하지 않음 |
| 영역별 달성률·손실점수 Top5·즉시과제 | Supabase 데이터에서 서버가 직접 계산 | 항목당 100점 정규화 기준 (원본에 항목별 가중치가 없음) |
| KCGS 공식등급, 3개년 등급추이, 벤치마킹 평균, 업종 분포, 의무공시 D-day, 환경 법규 위반 이력 | `backend/app/mock_data.py` | **샘플 값** — DN오토모티브는 사양서 §10 예시값을 그대로 사용, 하나마이크론은 대응 값이 없어 비워둠(화면에 "확인 필요"로 표시). 실사용 전 실제 KCGS 평가·컨설턴트 산정값으로 교체 필요 |
| AI 상담 패널 | **실제 RAG 챗봇** (Gemini + 문서 유사도 검색) | 아래 "AI 상담 챗봇" 절 참고 |

## AI 상담 챗봇 (RAG)

우측 AI 상담 패널은 실제로 동작하는 문서 기반 챗봇입니다.

- **문서 소스**: `db/chroma_db_migrated`에 2개사(DN오토모티브 007340 · 하나마이크론 067310)의
  사업보고서·기업지배구조보고서·지속가능경영보고서에서 추출한 텍스트/표 청크 7,755건이 들어
  있습니다. 다만 이 chroma DB는 벡터 인덱스(HNSW 실제 float 벡터)가 마이그레이션 과정에서
  유실된 상태라 원본 그대로는 유사도 검색이 안 됩니다 (원문·메타데이터는 sqlite에 온전함).
- 그래서 `backend/scripts/build_rag_index.py`가 두 회사분 청크만 골라 Gemini
  `gemini-embedding-001`(768차원)로 다시 임베딩해 `backend/data/rag_index.sqlite3`(약 35MB)로
  저장해 둡니다. 이미 실행해 결과물이 들어 있으니 다시 돌릴 필요는 없지만, 문서가 추가되거나
  다른 회사를 더 넣고 싶으면 스크립트의 `COMPANY_CODES`를 수정하고 재실행하면 됩니다
  (`backend` 디렉터리에서 `.venv\Scripts\python.exe scripts\build_rag_index.py`, 처음 실행한
  이 세션에서는 7,755건 임베딩에 약 5분 정도 걸렸습니다).
- **질의 흐름** (`backend/app/rag.py`):
  1. **질의 확장** — L3 항목 화면에서 묻는 질문이면 원 질문 그대로 + `항목명/카테고리/K-ESG
     점검기준 일부/데이터원천`으로 보강한 질문, 두 버전을 각각 임베딩해 검색하고 결과를
     id 기준으로 합쳐 최고 점수만 남긴다 (질의 확장으로 재현율 향상). 상위 8개 청크를 후보로 삼는다.
  2. **내부 채점 근거 주입** — L3 항목 컨텍스트가 있으면, Supabase에 이미 있는 해당 항목의
     K-ESG 점검기준·판단근거·확인근거·감점사유·개선방향을 "이미 검증된 사내 판단"으로 프롬프트에
     별도 블록으로 넣는다. 문서 재검색보다 훨씬 정확한 답을 만드는 핵심 장치다.
  3. **근거 우선 사고 단계** — 모델이 바로 결론을 쓰지 않고 `relevantFacts`(컨텍스트에서 질문과
     관련된 사실만 문장 단위로 추출, 화면에는 안 보임)를 먼저 채우게 한 뒤 그것만 근거로
     `conclusion`을 쓰도록 스키마·프롬프트로 강제한다.
  4. **대화 이력** — 프론트가 최근 답변 3개를 함께 보내 후속 질문("그럼 어떻게 해결해?")에도
     맥락을 이어 답한다.
  5. Gemini(`gemini-3.6-flash`, temperature 0.15)가 JSON 스키마로 결론/근거번호/다음행동을
     생성 → **인용은 모델이 지어내지 않고, 실제로 검색된 청크 중 모델이 실제 사용했다고 표시한
     것만** 구성합니다. 내부 채점 근거만으로 답했다면 인용 없이 결론만 나갑니다. 근거가 부족하면
     "근거 부족" 배지와 함께 솔직하게 답합니다 (사양서 F5-03 "인용 강제 답변" 대응).
  6. 근거 청크가 표(content_type='table')이면 원본 chroma DB의 `table_data`(행 배열 JSON,
     `backend/scripts/backfill_table_data.py`로 별도 백필)를 서버에서 `<table>` HTML로 변환해
     내려주고, AI 상담 패널이 마크다운 텍스트 대신 실제 표로 렌더링합니다.
  7. **근거 불충분 시 웹 검색 폴백** — 사내 문서(+내부 채점 근거)로도 `insufficientEvidence=true`가
     나오면 Gemini의 Google 검색 그라운딩(`tools: [{google_search:{}}]`)을 켠 별도 호출로 다시
     묻습니다. 인용은 모델이 본문에 적은 텍스트가 아니라 실제 `groundingMetadata.groundingChunks`
     (진짜 검색된 URL)에서만 만들고, 검색해도 관련 출처가 없으면 "찾지 못했습니다"라고 명시합니다
     — 출처 없는 웹 답변은 내려주지 않습니다. 화면에는 "웹 검색 근거" 배지와 클릭 가능한 출처
     링크로 구분해서 보여줍니다. (구조화 출력(responseSchema)과 검색 도구를 같은 요청에 같이 쓰면
     API가 에러 없이 응답은 주지만 실제로는 검색을 타지 않는 것을 확인해서, 이 경로만 순수 텍스트
     응답으로 분리했습니다.)
- **API 키**: `backend/.env`의 `GEMINI_API_KEY`. 이 키는 대화 중 평문으로 공유된 값이라
  이미 노출된 것으로 간주하는 것이 안전합니다 — [Google AI Studio](https://aistudio.google.com/apikey)에서
  폐기하고 새 키로 교체하는 것을 권장합니다. 키는 backend에만 있고 프론트엔드로는 절대 내려가지
  않습니다.
- **비용/한도**: 이 프로젝트가 쓰는 모델은 `gemini-embedding-001`(임베딩)과
  `gemini-3.6-flash`(생성)입니다. 원래 지정했던 `gemini-2.5-flash`는 이 키에서
  "새 사용자에게는 더 이상 제공되지 않음"으로 막혀 있어 대체했습니다 — 이후 이 모델도
  막히면 `backend/.env`의 `GEMINI_CHAT_MODEL`만 바꾸면 됩니다.

## 실행 방법

### 1) Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # SUPABASE_URL / SUPABASE_ANON_KEY 확인
uvicorn app.main:app --reload --port 8000
```

`.env`는 이미 이 프로젝트의 Supabase 프로젝트(`fwxlocorqedqfqkpulxo`) 값으로 채워져 있습니다.
anon key는 RLS가 꺼진 상태라 읽기 권한이 넓으니, 배포 전에는 RLS를 켜고 정책을 추가하는 것을
권장합니다.

확인: http://127.0.0.1:8000/api/health

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 접속 → 자동으로 `/companies/DN오토모티브/l1`로 이동합니다.
상단 앱바의 회사 셀렉터로 DN오토모티브 ↔ 하나마이크론을 전환할 수 있습니다.

`.env`의 `VITE_API_BASE`가 백엔드 주소(기본 `http://127.0.0.1:8000`)를 가리켜야 합니다.

### 3) (선택) UI 스모크 테스트

`frontend`에 Playwright가 devDependency로 들어 있습니다. 브라우저 없이도 렌더링을
확인하려면:

```bash
cd frontend
npx playwright install chromium   # 최초 1회
node -e "..."                     # 또는 직접 스크립트 작성 — chromium.launch → goto → screenshot
```

## 디렉터리 구조

```
backend/
  app/
    main.py            # FastAPI 라우트
    repository.py       # Supabase → 화면용 데이터 가공 (L1~L3)
    parsing.py           # 자유서식 텍스트 컬럼 파서 (근거충분성, 판단근거, 출처 캡션 등)
    mock_data.py           # DB에 없는 보조 데이터 (KCGS 등급 등, 샘플)
    report_data.py           # L4 — db/report_extracted_data.json(컨설팅 보고서 검증본) 조회
    benchmark_config.py       # L4 — 회사별 벤치마킹 대상 매핑
    roadmap.py                 # L5 — esg_roadmap_* 테이블 가공
    evidence_docs.py             # L6 — 참고자료 유형·근거충분성 집계
    company_profile.py             # L7 — esg_company_profile 조회
    supabase_client.py
    config.py
frontend/
  src/
    pages/            # L1Dashboard ~ L7Report
    components/         # AppShell, ExhibitCard, ConsultPanel, CriteriaPanel, DonutGauge 등
    context/              # CriteriaPanelContext
    styles/                 # tokens.css(디자인 토큰) / layout.css / components.css
    api/, hooks/, types.ts
data/                 # 원본 엑셀 (하나마이크론 · DN오토모티브)
db/                   # 사양서 원본 .md
```

## 알려진 한계 / 다음 단계

- `esg_diagnosis`에 항목별 실제 배점 가중치가 없어 전 항목을 100점 만점으로 정규화했습니다.
  원본 K-ESG 배점 구조(정보공시 150 / 환경 400 / 지배구조 450 / 업종특화 100 등)를 그대로
  반영하려면 항목별 가중치 컬럼이 추가로 필요합니다.
- 즉시 착수 과제 표에 예산·기간·담당부서가 없습니다 (원본 데이터 없음) — 컨설턴트가 채워 넣을
  별도 입력 체계가 필요합니다.
- `esg_diagnosis` 테이블은 RLS가 비활성 상태입니다 (요청에 따라 유지). 외부 공개 전 검토 필요.
- AI 상담은 L3(특정 항목) 컨텍스트가 있을 때 내부 채점 근거 덕분에 답변 품질이 좋습니다. 반면
  L1/L2처럼 특정 항목이 지정되지 않은 일반 질문은 여전히 문서 청크 코사인 유사도에만 의존하므로,
  질문이 문서의 정확한 용어를 안 쓰면 "근거 부족"으로 답할 수 있습니다 — 재순위화(re-ranking)나
  하이브리드(키워드+벡터) 검색을 추가하면 더 개선됩니다.
- `db/chroma_db_migrated`(2GB, 원본 청크 236,691건, DN오토모티브·하나마이크론 외 38개사 포함)는
  그대로 두었습니다. 다른 회사를 화면에 추가하려면 Supabase에 해당 회사의 `esg_diagnosis` 데이터를
  먼저 넣고, `build_rag_index.py`의 대상 회사 코드에도 추가해야 합니다.
- 기업코드·진단 항목 등 정적 참조 데이터는 백엔드가 TTL 5분짜리 캐시(`backend/app/cache_utils.py`)를
  쓰므로, Supabase 데이터를 직접 수정한 경우 최대 5분 후 자동 반영되거나 `POST /api/admin/clear-cache`
  호출로 즉시 반영할 수 있습니다(인증 없음, 로컬 개발 전용).
