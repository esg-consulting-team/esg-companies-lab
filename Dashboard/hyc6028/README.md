# ESG 진단 콘솔

`data/v1.1 ESG_대시보드_전체화면_사양서.md` 사양서의 화면 7개(L1~L7) 전체를 구현한 React(Vite)
프론트엔드 + Python(FastAPI) 백엔드입니다. 진단 채점 데이터는 Supabase의 정규화된
`esg_diagnostic_items`(항목 마스터, 42개) + `esg_diagnostic_scores`(회사별 채점, 하나마이크론/
DN오토모티브 각 42개 항목) 테이블을 조인해서 사용합니다 (원래는 평면 테이블 `esg_diagnosis` 하나였고,
그 테이블은 백업용으로 남아있습니다 — 자세한 내용은 사양서 §15.1 참고).

## 구조

```
backend/    FastAPI 서버 (Python) — Supabase에서 데이터를 읽어 대시보드용 API로 가공
frontend/   React(Vite) 앱 — 사양서 §13 디자인 시스템 토큰 적용, e2e 테스트(Playwright) 포함
frontend-design-preview/         디자인 시안 사본 — 팀 공유 DESIGN.md 반영 (원본 frontend는 미변경)
frontend-design-preview-wanted/  디자인 시안 사본 — 원티드/몽타주 디자인 시스템 반영 (원본 미변경)
data/       원본 xlsx/사양서
start-backend.bat   백엔드만 실행 (Windows)
start-frontend.bat  프론트엔드만 실행 (Windows)
start-all.bat       위 둘을 각각 새 창으로 동시에 실행 (Windows)
start-frontend-design-preview.bat         디자인 시안(DESIGN.md판) 실행, :5174
start-frontend-design-preview-wanted.bat  디자인 시안(원티드판) 실행, :5175
```

## 실행 방법 (Windows)

가장 쉬운 방법: 탐색기에서 **`start-all.bat`을 더블클릭**하세요. 새 창 2개가 뜨면서
백엔드(:8000)·프론트엔드(:5173)가 함께 실행됩니다. 개별 실행은 `start-backend.bat` /
`start-frontend.bat`을 각각 더블클릭하면 됩니다.

디자인 시안을 보려면 `start-frontend-design-preview.bat`(:5174) 또는
`start-frontend-design-preview-wanted.bat`(:5175)을 백엔드와 함께 띄우면 됩니다. 기존
`frontend`(:5173)와 포트가 겹치지 않아 세 개를 동시에 띄워 나란히 비교할 수 있습니다.

이 배치파일들은 **`venv`/`node_modules`가 없으면 자동으로 만들고 의존성을 설치**합니다.
그래서 다른 컴퓨터로 옮길 때는 `backend/venv`와 `frontend/node_modules`를 빼고 복사해도
됩니다 (용량이 크고 어차피 재설치되는 폴더입니다). 새 컴퓨터에는 미리 설치해둘 것만 있으면 됩니다:

- **Node.js** (LTS) — https://nodejs.org/ 에서 설치 (npm 포함)
- **Python 3.11+** — https://www.python.org/downloads/ 에서 설치. 설치 중
  **"Add python.exe to PATH" 체크 필수** — 체크하지 않으면 Windows의 Microsoft Store
  python 별칭이 대신 잡혀서 실행이 안 됩니다 (`start-backend.bat`이 이 상황을 자동으로 우회
  하려고 시도하긴 하지만, 처음부터 PATH에 잡혀 있는 쪽이 가장 안전합니다).

### 수동 실행 (참고용)

```bash
# 백엔드
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
venv\Scripts\python -m uvicorn app.main:app --port 8000

# 프론트엔드
cd frontend
npm install
npm run dev
```

- `backend/.env`에 이미 Supabase URL과 anon key가 들어 있습니다 (RLS로 읽기 전용만 허용).
- `frontend/.env`의 `VITE_API_BASE_URL`이 백엔드 주소(`http://127.0.0.1:8000`)를 가리킵니다.
- **주의**: 이 프로젝트가 OneDrive 동기화 폴더 안에 있으면 uvicorn `--reload` 옵션이 `venv/` 내
  수천 개 파일을 변경으로 오인해 무한 재시작 루프에 빠질 수 있습니다 (배치파일은 이 문제를 피하려고
  `--reload`를 쓰지 않습니다). 개발 중 자동 재시작이 필요하면 `--reload --reload-dir app`처럼
  감시 대상을 `app/` 폴더로 좁혀서 실행하세요.

## 테스트 (Playwright e2e)

`frontend/tests/dashboard.spec.js`에 L1~L7 화면을 실제 브라우저로 구동해 검증하는 e2e 테스트가
있습니다 (콘솔 에러 체크, 화면 간 이동, 기업 전환, 시뮬레이터 서버 재계산, XLSX 다운로드까지 확인).

```bash
cd frontend
npm install
npx playwright install chromium   # 브라우저 바이너리는 최초 1회만 설치하면 됨
npm run test:e2e                  # 헤드리스 실행
npm run test:e2e:ui               # Playwright UI 모드로 단계별 확인
```

백엔드·프론트엔드가 이미 떠 있으면 그 서버를 그대로 재사용하고, 안 떠 있으면
`playwright.config.js`의 `webServer` 설정이 알아서 둘 다 띄운 뒤 테스트를 실행합니다.

## 구현 범위

**구현 완료**
- L1 종합 현황: **실계산 D-day 밴드**, KPI 4종(가채점 총점 도넛게이지, E/S/G 미니칩), 영역별 달성률,
  KCGS 등급 매트릭스(연도별 종합/E/S/G 2단 서브헤더), 손실점수 Top5, **시급성 분포 도넛**, 즉시 착수
  과제(전체 스크롤 + 합계 sticky)
- L2 영역별 진단: 영역 탭, 근거충분성/시급성 필터, 항목 히트맵
- L3 항목 상세: 항목 리스트, 점검기준 원문, **서술형 진단 결과 카드**(현황/개선방향/후속액션 + 벤치마킹
  사례 아코디언, narrative 데이터가 없는 항목은 기존 확인근거/감점사유/해결방안 3분할로 자동 폴백)
- L4 비교 분석: 3축 선택기, 환경 원단위 추이, **벤치마킹 기업 카드**(hover 툴팁), 영역별 벤치마킹 갭,
  업종 등급 분포, **두 기업 비교 레이더 차트**(recharts)
- L5 개선 로드맵: **단계별 로드맵 과제**(시급성 배지 + hover 브레이크다운), 4개년 간트차트, ROI
  우선순위, 점수 시뮬레이터(서버 사이드 실시간 재계산)
- L6 증빙 데이터룸: 적재 문서 현황, 데이터 갭 리스트(실데이터 자동 추출), 업로드 드롭존(UI만)
- L7 리포트: 섹션 체크리스트, **XLSX 실제 다운로드**(항목별 채점 데이터), 생성 이력
- 기업 전환(하나마이크론 ↔ DN오토모티브), 공통 셸(앱바/레일/AI 패널 스텁)
- 시급성 배지 "?" 팝오버(회사별 판단기준, 데이터 없으면 자동 숨김) — 전 화면 공통

**미구현 (사양서 자체가 "확장" 단계로 표시한 기능)**
- F5 AI 상담(실제 임베딩 기반 답변) — 패널 UI만 존재하는 자리표시자
- L6 증빙 업로드의 실제 파싱/인덱싱 파이프라인 (F6-03)
- L7 PDF/PPTX 내보내기 (F6-04) — 현재는 XLSX만 실제 동작, 나머지는 501 응답

## 2차 고도화 (data/ 신규 자료 반영)

`data/esg_*.json` 8개 파일(컨설팅보고서 원문에서 추출한 실데이터)을 받아 아래를 추가했습니다. 이번엔
**하나마이크론·DN오토모티브 둘 다** 실제 근거가 있어서, KCGS 등급·벤치마킹·D-day는 두 회사 모두 실값이
채워져 있습니다 (1차 고도화 때 DN만 있던 것과 다름).

- **D-day 실계산**: `esg_disclosure_deadline`의 "고객사 해당 구간"/"실질 준비 기간" 원문을 정규식으로
  파싱해 tier·공시연도·착수기한을 계산합니다 (`backend/app/services/enrichment.py`의 `compute_dday`).
- **KCGS 등급 E/S/G 서브등급 + 벤치마킹 통합**: `esg_kcgs_grades`에 자사·벤치마킹 등급을
  `is_benchmark`/`benchmark_label`로 함께 저장, L1 Exhibit2가 연도별 종합/E/S/G 2단 표로 렌더링합니다.
- **항목별 서술형 근거**(`esg_item_narrative`, 77건): L3가 기존 정규식 파싱 대신 이 데이터를 우선
  사용합니다. 일부 항목(특히 DN 일부)은 narrative가 없어 기존 방식으로 자동 폴백합니다.
- **벤치마킹 기업 정보**(`esg_benchmark_companies`), **시급성 판단기준**(`esg_urgency_criteria`, 현재
  하나마이크론만 등록), **회사 프로필**(`esg_company_profile`), **로드맵 단계/과제**
  (`esg_roadmap_stages`/`esg_roadmap_tasks`, 비용·일정 없이 단계·산출물·연결항목 중심)를 각각
  `/api/companies/{company}/...` 엔드포인트로 노출합니다.

### 알아두면 좋은 것

- **이 테이블들은 제가 새로 만든 게 아니라 이미 이 Supabase 프로젝트에 존재하던 스키마**입니다(다른
  세션/도구가 먼저 만들어 둔 것으로 보이며, `company_id`로 `esg_companies`를 참조하는 정규화 구조).
  전부 RLS는 켜져 있는데 **정책이 하나도 없어서 앱(anon key)에서는 계속 0행으로 보이는 버그**가 있었고,
  읽기 정책을 추가해서 해결했습니다.
- 이 신규 테이블들을 조회하는 호출이 요청당 여러 번 늘어나면서, 기존에 "동시성 버그 회피용으로 매
  호출마다 새 Supabase 클라이언트를 만들던" 방식이 요청 하나에 10초 넘게 걸리는 회귀를 일으켰습니다.
  스레드별로 클라이언트를 캐시하도록(`backend/app/db.py`) 고쳐서 요청당 1~2초로 돌아왔고, 동시 요청
  테스트로 기존 동시성 버그가 재발하지 않는 것도 다시 확인했습니다.
- `data/ESG_대시보드_고도화_요약(v1.0_이후).md` 문서는 **이 프로젝트가 아닌 다른 코드베이스**(예:
  `backend/main.py`, `frontend/src/pages/L1.jsx`, `frontend-prev/` 등 이 저장소에 없는 경로)를
  기준으로 작성돼 있었습니다. 데이터(json 8개)만 가져와 이 프로젝트의 실제 구조에 맞게 새로 구현했고,
  파일 경로·컴포넌트명은 그 문서와 다릅니다.

## 3차 고도화 (진단 스키마 정규화 + 디자인 시안 2종)

- **`esg_diagnosis` → `esg_diagnostic_items`/`esg_diagnostic_scores` 마이그레이션**: 진단 채점의
  실제 소스가 평면 테이블 `esg_diagnosis`(84행) 하나였던 것을, 항목 마스터(`esg_diagnostic_items`,
  42행)와 회사별 채점(`esg_diagnostic_scores`, 84행)으로 정규화해 옮겼습니다. 두 테이블 다 PK/FK가
  없던 상태라 `esg_companies.id` PK, `esg_diagnostic_items.item_code` PK, `esg_diagnostic_scores`에
  identity PK + FK + `unique(company_id, item_code)`를 새로 추가했습니다. `backend/app/services/
  diagnosis.py`의 `fetch_items()`/`build_item_detail()`, `enrichment.py`의 `get_roadmap_plan()`이
  이 조인 쿼리를 쓰도록 바뀌었고, 반환 필드명은 기존과 동일하게 맞춰서 다른 서비스(roadmap/documents/
  reports)는 건드릴 필요가 없었습니다. 옛 `esg_diagnosis`는 백업용으로 남겨뒀습니다. 자세한 배경은
  `data/v1.1 ESG_대시보드_전체화면_사양서.md` §15.1 참고.
- **디자인 시안 2종(사본, 원본 미변경)**: `frontend-design-preview/`(팀 공유 DESIGN.md 반영),
  `frontend-design-preview-wanted/`(원티드/몽타주 디자인 시스템 반영). 위 "구조"/"실행 방법" 참고.

## 데이터에 대한 중요한 참고사항

- 원본 xlsx는 K-ESG 91개 항목 중 **E(환경)+G(지배구조) 42개 항목만** 채점되어 있습니다 (S/사회 제외).
- `esg_diagnostic_items`/`esg_diagnostic_scores` 외에 사양서 §10 목데이터를 옮겨 담은 보조 테이블(`company_meta`, `kcgs_grades`,
  `benchmark_grades`, `domain_benchmarks`, `documents`, `intensity_trends`,
  `sector_distribution_buckets`, `roadmap_tasks`, `report_exports`)을 만들었습니다. **KCGS 공식등급·
  벤치마킹 A~D사 비교·의무공시 D-day·환경 원단위 추이·업종 분포·로드맵 비용/일정은 DN오토모티브만
  사양서 예시값으로 채워져 있고, 하나마이크론은 실제 근거가 없어 비워뒀습니다** (UI에는 "미확인"/
  "데이터 없음"으로 정직하게 표시됩니다). 실제 운영 전에는 이 보조 테이블들을 각 회사의 실제 값으로
  교체해야 합니다.
- L4의 "영역별 벤치마킹 갭"은 항목 단위 벤치마킹 데이터가 없어 `domain_benchmarks`(영역 평균)를
  기준으로 계산한 근사치입니다. 사양서 원문의 항목 단위 갭(G-3-2 −100 등)과는 다른 수치입니다.
- L5 로드맵은 `roadmap_tasks`에 큐레이션 데이터가 있으면 그 값(비용·일정·담당자 포함)을 쓰고,
  없으면(하나마이크론) `esg_diagnostic_scores`/`esg_diagnostic_items`의 시급성·손실점수·해결방안에서
  자동 생성합니다 — 이 경우 비용/일정/담당자는 "미정"으로 표시됩니다.
- L7 XLSX 내보내기는 항목별 채점 데이터 전체를 실제로 내려받습니다. 사양서의 "마스터 채점표 수식
  셀 보존"은 구현하지 않았고(현재 셀 값만), PDF/PPTX는 아직 지원하지 않습니다.
- 항목 상세의 "확인근거/감점사유/해결방안" 텍스트는 xlsx의 `비고-채점모델`, `비고-손채점+AI채점`,
  `해결방안` 컬럼을 정규식으로 파싱한 결과입니다. 컬럼 서식이 크게 바뀌면 파싱이 깨질 수 있습니다
  (`backend/app/services/diagnosis.py`의 `parse_evidence`/`parse_solution` 참고).
