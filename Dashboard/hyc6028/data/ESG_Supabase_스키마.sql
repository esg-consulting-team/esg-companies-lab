-- ESG 진단 콘솔 — Supabase 실제 스키마 (2026-09-17 기준, live 조회 결과)
-- data/*.json 은 원본 소스일 뿐이고, 실제 저장 구조는 이 파일입니다.
-- (예: json의 "company": "하나마이크론" 문자열은 DB에서 esg_companies.id를 참조하는 company_id bigint FK로 정규화되어 있음)
--
-- RLS 공통 패턴: 아래 14개 테이블 전부 RLS enabled + 정책 1개만 존재
--   create policy "public read" on <table> for select using (true);
-- => anon/authenticated 키로 SELECT는 전부 가능, INSERT/UPDATE/DELETE는 정책이 없어 전부 차단됨(쓰기는 service_role 키 필요).
--
-- 참고용 문서이며, 실제로 이 SQL을 그대로 실행할 필요는 없습니다(이미 운영 중인 DB의 구조를 옮겨 적은 것).

-- 1. 기준 테이블 -------------------------------------------------

create table public.esg_companies (
  id bigint generated always as identity primary key,
  name text not null unique,
  created_at timestamptz not null default now(),
  stock_code text
);
-- rows: 2 (하나마이크론, DN오토모티브)

-- 2. 진단 항목 마스터 (K-ESG v2.0, 42개 항목) ---------------------

create table public.esg_diagnostic_items (
  item_code text primary key,
  apply_type text,
  area text,
  category text,
  item_name text,
  description text,
  data_source text,
  data_period text,
  data_scope text,
  formula text,
  scoring_type text,
  max_steps integer,
  score_structure_summary text,
  criteria_detail text,
  kssb_status text,
  kssb_reference text,
  other_reference text,
  source_file text,
  improvement_guide text,
  audit_question text,
  answer_format text
);
-- rows: 42

-- 3. 회사별 채점 결과 ---------------------------------------------

create table public.esg_diagnostic_scores (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  item_code text not null references public.esg_diagnostic_items(item_code),
  fulfilled_level text,
  violation_type_1 text,
  violation_type_2 text,
  violation_type_3 text,
  score numeric,
  note_2025 text,   -- 자동채점 판단 근거 (근거충분성: 충분/부분/불충분 텍스트 포함)
  note_2026 text,   -- 컨설턴트 검수 근거 ([라벨] 구간 파싱 대상)
  urgency text,      -- 즉시 / 중기 / 장기
  solution text,     -- [문제점]/[개선방향]/[필요근거] 구간 파싱 대상
  unique (company_id, item_code)
);
create index esg_diagnostic_scores_company_id_idx on public.esg_diagnostic_scores (company_id);
create index esg_diagnostic_scores_item_code_idx on public.esg_diagnostic_scores (item_code);
-- rows: 84 (42 items x 2 companies, 일부 미적용 항목은 score null)

-- 4. 항목별 배점 기준표 ---------------------------------------------
-- item_code에 FK를 걸지 않음(원본 코드 포맷이 diagnostic_items와 100% 일치하지 않아
-- FK 강제 시 insert 실패 위험 → 의도적으로 plain text 유지)

create table public.esg_score_scale (
  id bigint generated always as identity primary key,
  item_code text not null,
  item_name text,
  step_no integer,
  step_label text,
  score numeric,
  criteria text
);
create index esg_score_scale_item_code_idx on public.esg_score_scale (item_code);
-- rows: 313

-- 5. 지배구조 세부지표 (129개) --------------------------------------

create table public.esg_governance_indicators (
  indicator_code text primary key,
  seq integer,
  principle text,
  sub_principle text,
  indicator_name text,
  data_type text,
  data_source text,
  linked_esg_code text,
  note text
);
create index esg_governance_indicators_linked_esg_code_idx on public.esg_governance_indicators (linked_esg_code);
-- rows: 129

create table public.esg_governance_company_values (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  indicator_code text not null references public.esg_governance_indicators(indicator_code),
  value text,
  unique (company_id, indicator_code)
);
create index esg_governance_company_values_company_id_idx on public.esg_governance_company_values (company_id);
-- rows: 258

-- 6. KCGS 등급 (자사 + 벤치마킹 3개년) --------------------------------

create table public.esg_kcgs_grades (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  is_benchmark boolean not null default false,
  benchmark_label text,   -- is_benchmark=true일 때만 값 (A사/B사/C사 익명 코드)
  year integer not null,
  grade_overall text,
  grade_e text,
  grade_s text,           -- 참고용, 진단 대상 아님 (프론트에서 회색 처리)
  grade_g text
);
create index esg_kcgs_grades_company_id_year_idx on public.esg_kcgs_grades (company_id, year);
-- rows: 27

-- 7. 실행 로드맵 (4개년 단계 + 단계별 과제) ----------------------------

create table public.esg_roadmap_stages (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  stage_no integer not null,
  year integer,
  stage_name text,
  urgency_level text,   -- 보고서 원문 텍스트, 참고용 캡션일 뿐 배지 계산에는 미사용
  unique (company_id, stage_no)
);
create index esg_roadmap_stages_company_id_idx on public.esg_roadmap_stages (company_id);
-- rows: 8

create table public.esg_roadmap_tasks (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  stage_no integer not null,
  task_name text,
  related_item_codes text[],   -- esg_diagnostic_scores.urgency와 조인해 배지 집계 (backend/main.py expand_related_codes)
  deliverables text
);
create index esg_roadmap_tasks_company_id_stage_no_idx on public.esg_roadmap_tasks (company_id, stage_no);
-- rows: 40

-- 8. 신규 5개 테이블 (컨설팅보고서 서술형 데이터, 이번 세션에서 추가) -------

create table public.esg_item_narrative (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  item_code text not null,
  item_name text,
  fulfilled_level_text text,
  status text,          -- [현황]
  improvement text,     -- [개선방향]
  followup text,        -- [후속액션]
  benchmark_case text   -- null 허용, 있는 항목만 L3에서 아코디언 노출
);
create index esg_item_narrative_company_id_item_code_idx on public.esg_item_narrative (company_id, item_code);
-- rows: 77 (json 대비 company 문자열 -> company_id로 정규화된 것 외 동일)

create table public.esg_disclosure_deadline (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  key text not null,     -- 의무공시 적용 시점 / 고객사 해당 구간 / 실질 준비 기간 / 공급망 요구 / Scope 3 유예
  value text
);
create index esg_disclosure_deadline_company_id_idx on public.esg_disclosure_deadline (company_id);
-- rows: 10 (회사 2 x key 5) — backend에서 정규식으로 파싱해 D-Day 계산에 사용 (DEADLINE_TIER_RE, DEADLINE_PREP_RE)

create table public.esg_company_profile (
  id bigint generated always as identity primary key,
  company_id bigint not null unique references public.esg_companies(id),
  stock_code text,
  "설립연도" text,
  "상장구분" text,
  "주요사업" text,
  "연결자산총액" text,
  "업종분류" text,
  "종업원수" text
);
-- rows: 2 — 컬럼명이 한글 그대로(큰따옴표 식별자), 원본 json 필드명과 1:1

create table public.esg_benchmark_companies (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  benchmark_label text,   -- A사/B사/C사/D사
  industry text,
  grade_2025 text,
  rationale text          -- L4 벤치마킹 카드 hover 툴팁에 사용
);
create index esg_benchmark_companies_company_id_idx on public.esg_benchmark_companies (company_id);
-- rows: 7 (하나마이크론 3개사 + DN오토모티브 4개사)

create table public.esg_urgency_criteria (
  id bigint generated always as identity primary key,
  company_id bigint not null references public.esg_companies(id),
  level text,       -- 즉시 / 중기 / 장기
  criteria text      -- 전 화면 시급성 배지 "?" 팝오버에 사용
);
create index esg_urgency_criteria_company_id_idx on public.esg_urgency_criteria (company_id);
-- rows: 3 (하나마이크론만 존재 — DN오토모티브는 원본 소스 자체에 없음, 정상)

-- 9. RLS 정책 (14개 테이블 전부 동일 패턴) -----------------------------
-- alter table <table> enable row level security;
-- create policy "public read" on <table> for select using (true);
