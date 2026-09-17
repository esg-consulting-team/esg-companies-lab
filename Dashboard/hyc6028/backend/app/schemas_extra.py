from typing import Optional

from pydantic import BaseModel


class IntensityTrendRow(BaseModel):
    metric: str
    unit: Optional[str] = None
    y2023: Optional[float] = None
    y2024: Optional[float] = None
    y2025: Optional[float] = None
    cagr: Optional[float] = None
    verdict: Optional[str] = None
    formula_conflict: bool = False


class DomainGap(BaseModel):
    key: str
    label: str
    diff: float  # 자사 달성률(%) - 벤치마킹 평균(%) 포인트 차


class SectorBucket(BaseModel):
    grade: str
    company_count: int


class SectorDistribution(BaseModel):
    sector_label: Optional[str] = None
    total_companies: Optional[int] = None
    self_grade: Optional[str] = None
    buckets: list[SectorBucket]


class DomainTarget(BaseModel):
    key: str
    label: str
    achieved: float
    max_possible: float
    target: float  # 현실적 목표선: 만점 또는 벤치마킹 평균 중 낮은 쪽


class ComparisonResponse(BaseModel):
    intensity_trend: list[IntensityTrendRow]
    domain_gap: list[DomainGap]
    sector_distribution: Optional[SectorDistribution] = None
    domain_targets: list[DomainTarget]


class RoadmapTask(BaseModel):
    id: str
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    lane: str
    task: str
    start_month: Optional[str] = None
    months: Optional[int] = None
    gain: float
    cost: Optional[float] = None
    owner: Optional[str] = None
    dependency: Optional[str] = None
    curated: bool  # true = 큐레이션된 값, false = 실데이터 기반 자동 생성


class RoadmapResponse(BaseModel):
    tasks: list[RoadmapTask]
    has_curated_data: bool


class RoiRow(BaseModel):
    item_code: Optional[str] = None
    task: str
    gain: float
    cost: float
    cost_per_point: float


class SimulationRequest(BaseModel):
    task_ids: list[str]


class SimulationResponse(BaseModel):
    from_score: float
    to_score: float
    max_score: float
    gain: float
    rate_from: float
    rate_to: float
    total_cost: Optional[float] = None
    max_months: Optional[int] = None
    cost_unknown_count: int
    estimated: bool = True


class DocumentRow(BaseModel):
    name: str
    doc_type: Optional[str] = None
    year: Optional[int] = None
    size_label: Optional[str] = None
    parse_status: str
    linked_items: int


class DataGapRow(BaseModel):
    item_code: str
    item_name: str
    evidence_sufficiency: str
    required_evidence: Optional[str] = None


class DocumentRoomResponse(BaseModel):
    documents: list[DocumentRow]
    data_gaps: list[DataGapRow]


class ReportSection(BaseModel):
    no: str
    title: str
    pages: int


class ExportRecord(BaseModel):
    format: str
    sections: list[str]
    page_estimate: Optional[int] = None
    created_at: str


class ReportConfigResponse(BaseModel):
    sections: list[ReportSection]
    export_history: list[ExportRecord]


class ExportRequest(BaseModel):
    format: str  # xlsx/pdf/pptx
    section_nos: list[str]
