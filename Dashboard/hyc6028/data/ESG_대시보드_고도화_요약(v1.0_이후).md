# v1.0 사양서 이후 고도화 내역 (참고용 요약)

`ESG_대시보드_전체화면_사양서_v1.0_현재구현기준.md` 작성 이후 추가로 진행된 작업입니다. 이 문서엔 반영이 안 돼 있어서 따로 정리합니다. 각 항목에 관련 파일을 적어뒀으니, 코드 전체를 보지 않고도 필요한 부분만 찾아서 참고하시면 됩니다.

`frontend-prev/`가 가장 오래된 초안 스냅샷이고, `frontend/`가 지금 버전입니다. 같은 파일(`src/pages/L1.jsx` 등)을 두 폴더에서 diff 떠보면 화면 단위로 뭐가 달라졌는지 바로 보입니다.

## 1. 신규 Supabase 테이블 5개 연동
컨설팅보고서 원문에서 추출한 데이터를 새 테이블 5개로 적재하고 화면에 연결했습니다.

- 테이블: `esg_item_narrative`, `esg_disclosure_deadline`, `esg_company_profile`, `esg_benchmark_companies`, `esg_urgency_criteria`
- 원본 데이터: `data/esg_*.json` (이 문서와 같은 폴더)
- 백엔드 신규 엔드포인트: `backend/main.py`의 `/api/disclosure-deadline`, `/api/benchmark-companies`, `/api/urgency-criteria`, 그리고 `/api/items/{code}`에 `narrative` 필드 추가

### D-Day 자동계산 (하드코딩 → 실계산)
- `backend/main.py`: `DEADLINE_TIER_RE`, `DEADLINE_PREP_RE` 정규식으로 `esg_disclosure_deadline`의 "고객사 해당 구간"/"실질 준비 기간" 텍스트를 파싱 → `tier`/`applyYear`/`buildEndYear`/`prepYears` 산출
- `frontend/src/pages/L1.jsx`: `ddayText()`가 하드코딩 날짜 대신 `deadline.deadlineDate`로 D-Day 표시, 배너 문구 전체가 실데이터 기반으로 조립됨

### L3 항목상세 — 서술형 3분할 카드
- `frontend/src/pages/L3.jsx`: 기존 `solution` 파싱 대신 `esg_item_narrative`의 status/improvement/followup을 [현황]/[개선방향]/[후속액션] 3카드로 표시. `benchmark_case`가 있는 항목만 `<details>` 아코디언 노출, 없으면 섹션 자체 숨김. narrative 없는 항목은 기존 방식으로 폴백.

### L4 벤치마킹 카드
- `frontend/src/pages/L4.jsx` Exhibit "벤치마킹 기업 개요": `esg_benchmark_companies` 카드 그리드, hover 시 `rationale` 툴팁(`frontend/src/components/Tooltip.jsx`)

### 시급성 배지 물음표 팝오버 (전 화면 공통)
- `frontend/src/components/UrgencyHelp.jsx` + `Badges.jsx`의 `UrgencyTag`: 배지 옆 "?" 클릭 시 `esg_urgency_criteria.criteria`를 팝오버로 표시. 회사별로 다른 값(`CompanyContext.jsx`에서 회사 바뀔 때마다 재조회), 데이터 없는 회사는 "?" 자체가 안 뜸.

## 2. 차트 고도화 (recharts 도입)
`package.json`에 `recharts` 추가됨.

- `frontend/src/components/DonutGauge.jsx` — L1 KPI① 가채점 총점: 숫자 텍스트 → `RadialBarChart` 도넛 게이지
- `frontend/src/components/UrgencyDonut.jsx` — L1 Exhibit4 시급성 분포: 3-lane 막대 → `PieChart` 도넛 + 범례(건수/비율), 중앙에 총 건수 표시
- `frontend/src/pages/L4.jsx` 신규 Exhibit "영역별 레이더" — `RadarChart` 4축(정보공시/환경/지배구조/사회)에 하나마이크론·DN오토모티브 겹쳐서 비교. 사회(S)는 진단 대상 밖이라 0%로 표시(캡션 명시)

## 3. L5 로드맵 배지 — 개별 항목 시급성 브레이크다운
- 배지 자체의 "최고 시급성 우선" 계산 로직(`worst_urgency`)은 그대로 유지
- `backend/main.py`에 `codeUrgencies` 필드 추가: 과제에 연결된 `related_item_codes` 각각의 개별 urgency 값을 배열로 반환
- `frontend/src/pages/L5.jsx`: 배지에 hover하면 `P-1-1(즉시) · P-1-3(즉시)` 형태로 개별 코드별 근거를 툴팁으로 표시

## 4. L1 화면 마무리 폴리시
- **KPI② 공식등급**: 종합등급 칩 옆에 E/S/G 미니칩 추가(`EsgMiniChips`, S는 회색+툴팁 유지), 서브텍스트를 "{연도}년 기준"으로 축약
- **Exhibit5 즉시 착수 과제**: 8행만 보이던 것을 27건 전체 표시로 변경, `.exhibit-scroll`(max-height + overflow-y:auto)로 스크롤 처리, 합계 행은 `<tfoot>` + `position:sticky`로 하단 고정
- **전 화면 출처(source) 문구**: `esg_diagnostic_scores.solution` 같은 테이블/컬럼명 노출 → "2026년 채점 결과 기준 개선방안" 식 사람이 읽는 문구로 전면 교체 (L1/L2/L4/L5/L6 전체)
- **Exhibit2 KCGS 등급 매트릭스**: 셀마다 "E C"/"S B"처럼 라벨+값이 붙어 산만하던 걸 연도별 종합/E/S/G 2단 서브헤더 표로 재설계. 종합은 폰트 확대 + 색상 테두리 강조 유지, E/S/G는 축소 + 무채색, S는 회색 배경 유지

관련 CSS는 전부 `frontend/src/theme.css`에 있고 (`.grade-matrix`, `.exhibit-scroll`, `.urgency-help`, `.tooltip-wrap`, `.mini-egs` 등), `frontend-prev/src/theme.css`엔 없으니 클래스명 기준으로 diff해도 바로 구분됩니다.
