# ESG 진단 콘솔

`data/ESG_대시보드_전체화면_사양서.md` 사양서의 화면 7개(L1~L7) 전체를 구현한 React(Vite) 프론트엔드 +
Python(FastAPI) 백엔드입니다. 데이터는 Supabase(`esg_diagnosis` 테이블, 하나마이크론/DN오토모티브 각
42개 항목)를 사용합니다.

## 구조

```
backend/    FastAPI 서버 (Python) — Supabase에서 데이터를 읽어 대시보드용 API로 가공
frontend/   React(Vite) 앱 — 사양서 §13 디자인 시스템 토큰 적용, e2e 테스트(Playwright) 포함
data/       원본 xlsx/사양서
start-backend.bat   백엔드만 실행 (Windows)
start-frontend.bat  프론트엔드만 실행 (Windows)
start-all.bat       위 둘을 각각 새 창으로 동시에 실행 (Windows)
```

## 실행 방법 (Windows)

가장 쉬운 방법: 탐색기에서 **`start-all.bat`을 더블클릭**하세요. 새 창 2개가 뜨면서
백엔드(:8000)·프론트엔드(:5173)가 함께 실행됩니다. 개별 실행은 `start-backend.bat` /
`start-frontend.bat`을 각각 더블클릭하면 됩니다.

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
- L1 종합 현황: D-day 밴드, KPI 4종, 영역별 달성률, KCGS 등급 매트릭스, 손실점수 Top5, 즉시 착수 과제
- L2 영역별 진단: 영역 탭, 근거충분성/시급성 필터, 항목 히트맵
- L3 항목 상세: 항목 리스트, 점검기준 원문, 확인근거/감점사유, 해결방안 3분할, 실사 질문
- L4 비교 분석: 3축 선택기(시점/대상/기준), 환경 원단위 추이, 영역별 벤치마킹 갭, 업종 등급 분포
- L5 개선 로드맵: 4개년 간트차트, ROI 우선순위, 점수 시뮬레이터(서버 사이드 실시간 재계산)
- L6 증빙 데이터룸: 적재 문서 현황, 데이터 갭 리스트(실데이터 자동 추출), 업로드 드롭존(UI만)
- L7 리포트: 섹션 체크리스트, **XLSX 실제 다운로드**(항목별 채점 데이터), 생성 이력
- 기업 전환(하나마이크론 ↔ DN오토모티브), 공통 셸(앱바/레일/AI 패널 스텁)

**미구현 (사양서 자체가 "확장" 단계로 표시한 기능)**
- F5 AI 상담(실제 임베딩 기반 답변) — 패널 UI만 존재하는 자리표시자
- L6 증빙 업로드의 실제 파싱/인덱싱 파이프라인 (F6-03)
- L7 PDF/PPTX 내보내기 (F6-04) — 현재는 XLSX만 실제 동작, 나머지는 501 응답

## 데이터에 대한 중요한 참고사항

- 원본 xlsx는 K-ESG 91개 항목 중 **E(환경)+G(지배구조) 42개 항목만** 채점되어 있습니다 (S/사회 제외).
- `esg_diagnosis` 외에 사양서 §10 목데이터를 옮겨 담은 보조 테이블(`company_meta`, `kcgs_grades`,
  `benchmark_grades`, `domain_benchmarks`, `documents`, `intensity_trends`,
  `sector_distribution_buckets`, `roadmap_tasks`, `report_exports`)을 만들었습니다. **KCGS 공식등급·
  벤치마킹 A~D사 비교·의무공시 D-day·환경 원단위 추이·업종 분포·로드맵 비용/일정은 DN오토모티브만
  사양서 예시값으로 채워져 있고, 하나마이크론은 실제 근거가 없어 비워뒀습니다** (UI에는 "미확인"/
  "데이터 없음"으로 정직하게 표시됩니다). 실제 운영 전에는 이 보조 테이블들을 각 회사의 실제 값으로
  교체해야 합니다.
- L4의 "영역별 벤치마킹 갭"은 항목 단위 벤치마킹 데이터가 없어 `domain_benchmarks`(영역 평균)를
  기준으로 계산한 근사치입니다. 사양서 원문의 항목 단위 갭(G-3-2 −100 등)과는 다른 수치입니다.
- L5 로드맵은 `roadmap_tasks`에 큐레이션 데이터가 있으면 그 값(비용·일정·담당자 포함)을 쓰고,
  없으면(하나마이크론) `esg_diagnosis`의 시급성·손실점수·해결방안에서 자동 생성합니다 — 이 경우
  비용/일정/담당자는 "미정"으로 표시됩니다.
- L7 XLSX 내보내기는 항목별 채점 데이터 전체를 실제로 내려받습니다. 사양서의 "마스터 채점표 수식
  셀 보존"은 구현하지 않았고(현재 셀 값만), PDF/PPTX는 아직 지원하지 않습니다.
- 항목 상세의 "확인근거/감점사유/해결방안" 텍스트는 xlsx의 `비고-채점모델`, `비고-손채점+AI채점`,
  `해결방안` 컬럼을 정규식으로 파싱한 결과입니다. 컬럼 서식이 크게 바뀌면 파싱이 깨질 수 있습니다
  (`backend/app/services/diagnosis.py`의 `parse_evidence`/`parse_solution` 참고).
