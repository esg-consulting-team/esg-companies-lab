from typing import Optional

from pydantic import BaseModel


class CompanyMeta(BaseModel):
    company: str
    sector: Optional[str] = None
    stock_code: Optional[str] = None
    disclosure_phase: Optional[int] = None
    deadline_date: Optional[str] = None
    phase_confirmed: bool = False


class DomainSummary(BaseModel):
    key: str
    label: str
    items: int
    achieved: float  # sum of item scores (0-100 each)
    max_possible: float  # items * 100
    achievement_rate: float  # achieved / max_possible
    benchmark_avg: Optional[float] = None  # fraction 0~1, None if not available


class YearGrade(BaseModel):
    overall: Optional[str] = None
    e: Optional[str] = None
    s: Optional[str] = None
    g: Optional[str] = None


class GradeTrendRow(BaseModel):
    alias: str
    self_company: bool
    grades: dict[str, YearGrade]  # year(str) -> YearGrade


class DdayInfo(BaseModel):
    tier: Optional[int] = None
    apply_year: Optional[int] = None
    build_start_year: Optional[int] = None
    build_end_year: Optional[int] = None
    prep_years: Optional[int] = None
    deadline_date: Optional[str] = None
    days_left: Optional[int] = None
    tier_text: Optional[str] = None
    prep_text: Optional[str] = None


class GapItem(BaseModel):
    item_code: str
    item_name: str
    domain: str
    score: float
    lost_points: float


class UrgencyCounts(BaseModel):
    즉시: int
    중기: int
    장기: int


class ImmediateTask(BaseModel):
    item_code: str
    item_name: str
    urgency: str
    score: float
    lost_points: float
    direction: str  # parsed [개선방향] text
    owner_hint: Optional[str] = None


class KpiSummary(BaseModel):
    total_score: float
    max_score: float
    achievement_rate: float
    prev_total_score: Optional[float] = None
    insufficient_evidence_items: int
    applicable_items: int
    recoverable_by_evidence: int


class DashboardSummary(BaseModel):
    company: CompanyMeta
    kpi: KpiSummary
    domains: list[DomainSummary]
    grade_trend: list[GradeTrendRow]
    official_grade: Optional[str] = None
    gap_top: list[GapItem]
    urgency_counts: UrgencyCounts
    immediate_tasks: list[ImmediateTask]
    documents_count: int
    dday: Optional[DdayInfo] = None


class ItemHeatCell(BaseModel):
    item_code: str
    item_name: str
    category: str
    score: float
    evidence_sufficiency: str  # 충분/부분/불충분/미확인
    urgency: str
    scoring_type: str
    sector_specific: bool


class DomainItemsResponse(BaseModel):
    domain_key: str
    label: str
    items: list[ItemHeatCell]
    achieved: float
    max_possible: float


class EvidenceBlock(BaseModel):
    evidence_sufficiency: str
    confirmed_basis: Optional[str] = None
    reference_pages: Optional[str] = None
    deduction_note: Optional[str] = None


class SolutionBlock(BaseModel):
    current_problem: Optional[str] = None
    direction: Optional[str] = None
    required_evidence: Optional[str] = None


class NarrativeBlock(BaseModel):
    fulfilled_level_text: Optional[str] = None
    status: Optional[str] = None
    improvement: Optional[str] = None
    followup: Optional[str] = None
    benchmark_case: Optional[str] = None


class ItemDetail(BaseModel):
    item_code: str
    item_name: str
    domain: str
    category: str
    score: float
    max_score: float = 100
    evidence_sufficiency: str
    urgency: str
    scoring_type: str
    application_type: Optional[str] = None
    criteria_detail: Optional[str] = None
    guideline_background: Optional[str] = None
    evidence: EvidenceBlock
    solution: SolutionBlock
    audit_question: Optional[str] = None
    answer_format: Optional[str] = None
    kssb_status: Optional[str] = None
    kssb_reference: Optional[str] = None
    other_reference_standards: Optional[str] = None
    narrative: Optional[NarrativeBlock] = None
