# schema_config.py
# 실제 Supabase 스키마 확인 완료 (2026-09-18 기준) 반영.
# 논리명 -> 실제 테이블/컬럼명 매핑. 코드에서는 이 딕셔너리로만 접근하고
# 테이블/컬럼명을 직접 하드코딩하지 말 것 -> 스키마 바뀌면 여기만 수정.

TABLE_MAP = {
    # ── 레거시: 실제 대시보드 화면 숫자의 원천 (회사 단위 연도별 점수/등급) ──
    "company_score_yearly": {
        "table": "company_esg_yearly",
        "company_key_col": "기업코드",              # companies.기업코드 FK로 연결됨
        "year_col": "평가년도",
        "grade_overall_col": "esg등급",
        "grade_e_col": "esg환경",
        "grade_s_col": "esg사회",
        "grade_g_col": "esg지배구조",
        "score_avg_col": "채점평균",
        "score_disclosure_col": "채점공시",
        "score_env_col": "채점환경",
        "score_gov_col": "채점지배구조",
        "score_avg_excl_semi_col": "채점평균_반도체제외",   # 이미 사전 계산됨, 재계산 금지
        "score_disclosure_excl_semi_col": "채점공시_반도체제외",
        "score_env_excl_semi_col": "채점환경_반도체제외",
        "score_gov_excl_semi_col": "채점지배구조_반도체제외",
        "total_assets_col": "자산총액",
        "report_published_col": "보고서발행여부",
    },
    "companies_legacy": {
        "table": "companies",
        "code_col": "기업코드",
        "name_col": "기업명",
        "is_semiconductor_col": "반도체회사여부",
    },

    # ── 항목 상세: FK 없음, company는 텍스트로 직접 매칭 (.eq 사용) ──
    "diagnosis": {
        "table": "esg_diagnosis",
        "company_match_col": "company",             # 조인 불가, 텍스트 일치로만 조회
        "item_code_col": "classification_code",
        "item_name_col": "item_name",
        "domain_col": "domain",
        "score_col": "score",
        "urgency_col": "urgency",
        "solution_col": "solution",
        "criteria_col": "criteria_detail",
        "kssb_status_col": "kssb_status",
    },

    # ── 신규(컨설팅보고서 추출): 전부 esg_companies.id로 FK 연결됨 ──
    "esg_companies": {
        "table": "esg_companies",
        "id_col": "id",
        "name_col": "name",
        "stock_code_col": "stock_code",
    },
    "item_narrative": {
        "table": "esg_item_narrative",
        "company_id_col": "company_id",
        "item_code_col": "item_code",
        "item_name_col": "item_name",
        "fulfilled_level_col": "fulfilled_level_text",
        "status_col": "status",
        "improvement_col": "improvement",
        "followup_col": "followup",
        "benchmark_case_col": "benchmark_case",     # 없을 수 있음(nullable) - 프론트에서 없으면 섹션 숨김
    },
    "company_profile": {
        "table": "esg_company_profile",
        "company_id_col": "company_id",
        "founded_year_col": "설립연도",
        "listing_type_col": "상장구분",
        "main_business_col": "주요사업",
        "total_assets_col": "연결자산총액",
        "industry_col": "업종분류",
        "employees_col": "종업원수",
    },
    "disclosure_deadline": {
        "table": "esg_disclosure_deadline",
        "company_id_col": "company_id",
        "key_col": "key",
        "value_col": "value",
    },
    "benchmark_companies": {
        "table": "esg_benchmark_companies",
        "company_id_col": "company_id",
        "label_col": "benchmark_label",
        "industry_col": "industry",
        "grade_2025_col": "grade_2025",
        "rationale_col": "rationale",
    },
    "kcgs_grades": {
        "table": "esg_kcgs_grades",
        "company_id_col": "company_id",
        "is_benchmark_col": "is_benchmark",
        "benchmark_label_col": "benchmark_label",
        "year_col": "year",
        "grade_overall_col": "grade_overall",
        "grade_e_col": "grade_e",
        "grade_s_col": "grade_s",
        "grade_g_col": "grade_g",
    },
    "roadmap_stages": {
        "table": "esg_roadmap_stages",
        "company_id_col": "company_id",
        "stage_no_col": "stage_no",
        "year_col": "year",
        "stage_name_col": "stage_name",
        "urgency_level_col": "urgency_level",       # 보고서 원문 텍스트, 하나마이크론만 값 있음(참고용 캡션 전용)
    },
    "roadmap_tasks": {
        "table": "esg_roadmap_tasks",
        "company_id_col": "company_id",
        "stage_no_col": "stage_no",
        "task_name_col": "task_name",
        "related_item_codes_col": "related_item_codes",  # ARRAY 타입, esg_diagnosis.classification_code와 조인해 urgency 집계
        "deliverables_col": "deliverables",
    },
    "urgency_criteria": {
        "table": "esg_urgency_criteria",
        "company_id_col": "company_id",
        "level_col": "level",
        "criteria_col": "criteria",
    },
}

# DB 테이블이 아닌 정적 참조 파일 - SQL 조회 대상 아님, 직접 로드해서 사용
STATIC_REFERENCE_FILE = "db/report_extracted_data.json"
