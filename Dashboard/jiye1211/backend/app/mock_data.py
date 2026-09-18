"""DB(esg_diagnosis)에 없는 보조 데이터.

벤치마킹 평균, 업종 등급분포, 환경 법규 위반 이력 등은 현재 Supabase에 적재된 원본 엑셀
(01_ESG통합진단마스터)에 없는 정보다. KCGS 공식등급·등급추이와 의무공시 적용시기는 더 이상 이
파일이 아니라 company_esg_yearly 테이블에서 계산한다
(repository.fetch_grade_history, repository.compute_disclosure_roadmap 참고).

- DN오토모티브 값은 사양서(ESG_대시보드_전체화면_사양서_v2.md §10 목데이터)에 이미 예시로 주어진
  수치를 그대로 가져왔다 — 사양서 작성자가 준비한 데모용 값이며 실제 KCGS 평가 결과가 아니다.
- 하나마이크론은 사양서에 대응 값이 없어 임의로 지어내지 않았다. null로 두고 프론트엔드가
  "확인 필요" 상태로 표시하도록 한다.

이 파일 전체는 실사용 전 실제 데이터 소스(컨설턴트 산정값 등)로 교체돼야 한다.
"""
from typing import Any, Optional, TypedDict


class KeyIssue(TypedDict):
    title: str
    body: str


class CompanyProfile(TypedDict, total=False):
    companyId: Optional[str]
    sector: Optional[str]
    # 계산된 의무공시 로드맵(2030년 시작 등)이 컨설팅 보고서 원문 서술과 다를 때만 채운다.
    # 계산 로직 자체에는 영향 없음 — 화면에 병기하는 각주 텍스트일 뿐이다.
    disclosureRoadmapCaveat: Optional[str]
    benchmarkAvgByBucket: dict[str, float]
    sectorDistribution: Optional[dict[str, Any]]
    violations: list[dict[str, Any]]
    # L1 상단 "핵심 문제 3장" — 컨설팅 보고서 원문 그대로(report_extracted_data.json엔 없는 문구).
    # 요약·수정 없이 원문 그대로 옮겼다.
    keyIssues: list[KeyIssue]
    isMock: bool


# companies.산업코드(KSIC) → 업종명. 지금 화면에 나오는 회사의 코드만 확인된 값을 채운다 —
# 모르는 코드를 임의로 채우지 않는다(L1 프로필 줄에서 코드만 표시하고 이름은 생략됨).
INDUSTRY_NAMES: dict[str, str] = {
    "C2611": "반도체 및 관련 부품 제조업",
}


COMPANY_PROFILES: dict[str, CompanyProfile] = {
    "DN오토모티브": {
        "companyId": "007340",
        "sector": "운송장비·부품",
        "disclosureRoadmapCaveat": None,
        "benchmarkAvgByBucket": {
            "disclosure": 0.84,
            "environment": 0.82,
            "governance": 0.79,
            "sector": 0.71,
        },
        "sectorDistribution": {
            "sector": "운송장비·부품",
            "total": 76,
            "selfGrade": "D",
            "buckets": {"A+": 1, "A": 8, "B+": 12, "B": 15, "C": 18, "D": 22},
        },
        "violations": [
            {
                "date": "2024-03-06",
                "site": "양산3공장",
                "title": "대기배출시설 변경신고 미이행",
                "law": "대기환경보전법 제23조 2항",
                "authority": "양산시청",
                "penalty": "과태료 48만원",
                "type": "유형2",
                "deduction": -30,
            }
        ],
        "keyIssues": [
            {"title": "①", "body": "정보공시 영역에 충족 판정 항목이 없다"},
            {"title": "②", "body": "환경 정량데이터가 공시되지 않는다"},
            {"title": "③", "body": "미충족 항목이 주주권과 보상 공시에 집중되어 있다"},
        ],
        "isMock": True,
    },
    "하나마이크론": {
        "companyId": None,
        "sector": "반도체 후공정",
        "disclosureRoadmapCaveat": "컨설팅 보고서는 FY2029로 기재 — 자산 성장 전망 반영 여부 확인 필요",
        "benchmarkAvgByBucket": {},
        "sectorDistribution": None,
        "violations": [],
        "keyIssues": [
            {"title": "①", "body": "지배구조가 종합등급을 끌어내리는 단일 병목이다"},
            {"title": "②", "body": "해외사업장과 종속회사의 환경데이터가 연결 경계를 대표하지 못한다"},
            {"title": "③", "body": "ESG 목표가 경영진 성과평가와 보상에 연결되지 않는다"},
        ],
        "isMock": True,
    },
}


def get_company_profile(company: str) -> CompanyProfile:
    return COMPANY_PROFILES.get(
        company,
        {
            "companyId": None,
            "sector": None,
            "disclosureRoadmapCaveat": None,
            "benchmarkAvgByBucket": {},
            "sectorDistribution": None,
            "violations": [],
            "keyIssues": [],
            "isMock": True,
        },
    )
