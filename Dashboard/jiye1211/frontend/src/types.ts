// 백엔드(FastAPI) 응답 구조와 1:1로 맞춘 타입. backend/app/repository.py 참고.

export type EvidenceLevel = "충분" | "부분" | "불충분" | null;
export type Urgency = "즉시" | "중기" | "장기" | null;
export type DomainBucketKey = "disclosure" | "environment" | "governance" | "sector";

export interface CompanyRef {
  name: string;
  sector: string | null;
  id: string | null;
}

/** 의무공시 적용시기 — 금융위원회 지속가능성 공시 제도화 방안(최종안), 2026.7 확정 로드맵 기준으로
 * company_esg_yearly 최신 연도 자산총액에서 계산(회사별 하드코딩 없음). backend/app/repository.py
 * compute_disclosure_roadmap 참고. */
export interface DisclosureRoadmap {
  status: "applicable" | "not_applicable" | "unknown";
  totalAssets: number | null;
  disclosureStartYear: number | null;
  deadlineDate: string | null; // YYYY-MM-DD, 3개년 추세 확보 착수 기한
  scope3GraceYear: number | null;
}

/** L1 상단 기업 프로필 한 줄 — companies + company_esg_yearly 최신 연도 값 조합.
 * industryName은 확인된 산업코드만 채워진다(모르는 코드는 null, 임의로 채우지 않음). */
export interface IndustryProfile {
  market: string | null;
  industryCode: string | null;
  industryName: string | null;
  totalAssets: number | null;
  assetTier: string | null;
}

export interface CompanyInfo {
  name: string;
  id: string | null;
  sector: string | null;
  disclosureRoadmap: DisclosureRoadmap;
  /** 계산값이 컨설팅 보고서 원문 서술과 다를 때만 채워지는 각주(예: 하나마이크론 FY2029 서술). */
  disclosureRoadmapCaveat: string | null;
  industryProfile: IndustryProfile;
}

/** L1 상단 "핵심 문제 3장" — 컨설팅 보고서 원문 그대로(회사별 고정 문구, report_extracted_data.json엔 없음). */
export interface KeyIssue {
  title: string;
  body: string;
}

export interface AssessmentInfo {
  year: number;
  framework: string;
  totalScore: number;
  maxScore: number;
  rate: number | null;
  applicableItems: number;
  totalItems: number;
}

export interface OfficialGrade {
  source: string;
  year: number;
  overall: string;
}

/** company_esg_yearly 기반 최근 3개년 KCGS 공식등급. 해당 연도 행이 없으면 필드가 전부 null. */
export interface GradeHistoryYear {
  year: number;
  overall: string | null;
  environment: string | null;
  social: string | null;
  governance: string | null;
}

export interface DomainSummary {
  key: DomainBucketKey;
  label: string;
  items: number;
  score: number;
  max: number;
  benchmarkAvg: number | null;
  rate: number | null;
}

export interface LossItem {
  code: string;
  name: string;
  lostPoints: number;
  domainLabel: string;
}

export interface ImmediateTask {
  code: string;
  name: string;
  domainLabel: string;
  currentScore: number;
  potentialGain: number;
  scoringType: string | null;
  solution: string | null;
}

export interface SimulationResult {
  scope: string;
  from: number;
  to: number;
  gain: number;
  rateFrom: number | null;
  rateTo: number | null;
  estimated: boolean;
}

export interface EvidenceCounts {
  충분: number;
  부분: number;
  불충분: number;
  미평가: number;
}

export interface UrgencyCounts {
  즉시: number;
  중기: number;
  장기: number;
}

export interface CompanySummary {
  company: CompanyInfo;
  assessment: AssessmentInfo;
  officialGrade: OfficialGrade | null;
  gradeHistory: GradeHistoryYear[];
  domains: DomainSummary[];
  evidenceCounts: EvidenceCounts;
  urgencyCounts: UrgencyCounts;
  lossTop5: LossItem[];
  immediateTasks: ImmediateTask[];
  simulation: SimulationResult;
  keyIssues: KeyIssue[];
  isMock: boolean;
}

export interface ItemSummary {
  code: string;
  name: string;
  category: string | null;
  domainBucket: DomainBucketKey;
  domainLabel: string;
  applicationType: string | null;
  scoringType: string | null;
  maxStageCount: number | null;
  currentStage: number | null;
  score: number | null;
  scoreRaw: string | null;
  max: number | null;
  applicable: boolean;
  evidence: EvidenceLevel;
  urgency: Urgency;
  solution: string | null;
  improvementGuide: string | null;
  dataSource: string | null;
}

export interface Violation {
  date: string;
  site: string;
  title: string;
  law: string;
  authority: string;
  penalty: string;
  type: string;
  deduction: number;
}

export interface DomainDetail {
  bucket: DomainBucketKey;
  label: string;
  items: ItemSummary[];
  summary: { itemCount: number; score: number; max: number; rate: number | null };
  evidenceCounts: Record<string, number>;
  urgencyCounts: Record<string, number>;
  scoringTypeCounts: Record<string, number>;
  violations: Violation[];
  isMock: boolean;
}

export interface ScoringNote {
  raw: string;
  structured: boolean;
  summaryLine?: string;
  judgmentBasis?: string;
  confirmedBasis?: string;
  deductionReason?: string;
  requiredEvidenceNote?: string;
}

export interface SolutionSplit {
  raw: string;
  structured: boolean;
  problem?: string;
  direction?: string;
  evidence?: string;
}

export interface ChatCitation {
  n: number;
  doc: string;
  page?: number | null;
  snippet?: string;
  score?: number;
  /** 근거가 표 청크일 때만 내려오는, 서버에서 만든 안전한 <table> 마크업 (셀 텍스트는 이스케이프됨). */
  tableHtml?: string;
  /** 웹 검색 근거일 때만: 실제 출처 URL. 있으면 doc/snippet 대신 링크로 렌더링한다. */
  url?: string;
  source?: "doc" | "web";
}

export interface ChatResponse {
  conclusion: string;
  citations: ChatCitation[];
  nextAction: string;
  insufficientEvidence: boolean;
  /** true면 사내 문서로 답이 안 돼 Google 검색으로 보충한 답변. */
  viaWebSearch?: boolean;
}

export interface PendingReview {
  itemCode: string;
  currentScore: number;
  pendingReason: string;
}

export interface ItemDetail extends ItemSummary {
  itemDescription: string | null;
  dataPeriod: string | null;
  dataScope: string | null;
  dataFormula: string | null;
  scoreStructureSummary: string | null;
  criteriaDetail: string | null;
  kssbStatus: string | null;
  kssbReference: string | null;
  otherReferenceStandards: string | null;
  dueDiligenceQuestion: string | null;
  answerFormat: string | null;
  scoringNote: ScoringNote;
  solutionSplit: SolutionSplit;
  /** "판정 확인 중" 항목이면 채워진다 — db/report_extracted_data.json의 pendingItems. */
  pendingReview: PendingReview | null;
  /** "출처: 문서명 p.페이지" 캡션용 — note_scoring_model_25(근거페이지:)/note_manual_ai_scoring_26
   * ([확인근거])에서 추출한 근사치. 못 찾으면 빈 배열(이 경우 캡션 자체를 렌더링하지 않는다). */
  evidenceSources: string[];
}

// ── L4 비교 분석 — db/report_extracted_data.json을 그대로 반영 (필드명도 원본 JSON과 동일) ──

export interface GroupedTrendGroup {
  itemCount: number;
  items_example?: string[];
  selfScoreRange_2023to2025?: [number, number];
  benchmarkAvgRange_2023to2025?: [number, number];
  gapRange?: [number, number];
  selfVsBenchmarkDeltaRange?: [number, number];
  selfScore_2023?: number;
  selfScore_2025?: number;
  benchmarkAvg_2025?: number;
  gap_2025?: number;
  note?: string;
}

export interface GroupedScoreTrend {
  dependentOnReport: GroupedTrendGroup;
  independentOfReport: GroupedTrendGroup;
  note_dataConfidence?: string;
  overallAvgTrend?: { "2023": number; "2025": number; note?: string };
}

export interface PrecedentCase {
  benchmarkAlias: string;
  itemCodes: string[];
  before: number;
  after?: number;
  afterRange?: [number, number];
  beforeYear?: number;
  afterYear?: number;
  months: number;
  note: string;
}

export interface CorrelationRow {
  itemCode: string;
  itemName: string;
  self: number;
  benchmarkAvg: number;
  gap: number;
  rho: number | null;
  rhoNote?: string;
}

export interface DomainScoreCompare {
  domain: string;
  self: number;
  benchmarkAvg: number;
  gap: number;
  note?: string;
}

export interface BenchmarkMissingDomain {
  company: string;
  domain: string;
  note: string;
}

export interface NextDiagnosis {
  fullRediagnosis: string;
  partialCheck: string;
  monitoringCycle: string;
}

export interface ReportComparison {
  applicableItems: number;
  itemBreakdown: Record<string, number>;
  note_applicableItems?: string;
  benchmarkCompanyCount: number;
  benchmarkAliases: string[];
  benchmarkMissingDomains: BenchmarkMissingDomain[];
  totalScore: { self: number; benchmarkAvg: number; gap: number; scale: string };
  domainScores?: DomainScoreCompare[];
  /** 도메인별 · 회사별 채점값(보고서 원문 그대로) — 지금은 하나마이크론의 "반도체특화"만 존재.
   * 값이 null이면 그 회사가 해당 도메인에서 미채점이라는 뜻. */
  domainScoresByCompany?: Record<string, Record<string, number | null>>;
  note_domainScoresByCompany?: string;
  groupedScoreTrend: GroupedScoreTrend;
  structuralZeroItems_3yearConsecutive: string[];
  precedentCases: PrecedentCase[];
  kcgsCorrelation: CorrelationRow[] | null;
  note_kcgsCorrelation?: string;
  pendingItems: PendingReview[];
  note_pendingItems?: string;
  generalLimitations: string[];
  nextDiagnosis: NextDiagnosis;
}

/** L4 "자사 vs 벤치마킹군" Exhibit — company_esg_yearly 최신 연도 도메인별 채점값.
 * 업종특화/반도체특화는 이 테이블에 별도 컬럼이 없어 포함하지 않는다. */
export interface DomainBenchmarkCompany {
  company: string;
  year: number;
  overall: number | null;
  disclosure: number | null;
  environment: number | null;
  governance: number | null;
}

export interface DomainBenchmarkResponse {
  self: DomainBenchmarkCompany | null;
  peers: DomainBenchmarkCompany[];
}

// ── L5 개선 로드맵 — esg_roadmap_stages/esg_roadmap_tasks/esg_urgency_criteria/esg_disclosure_deadline ──

export type RoadmapChipType = "item" | "non_scoring" | "domain";

/** related_item_codes(자유서식) 한 항목을 화면이 그대로 렌더링할 칩으로 정리한 것.
 * type="item"이면 code로 L3 이동, type="domain"이면 bucket으로 L2 탭 이동, type="non_scoring"이면 링크 없음. */
export interface RoadmapChip {
  type: RoadmapChipType;
  label: string;
  code: string | null;
  bucket: DomainBucketKey | null;
  raw: string;
}

export interface RoadmapTask {
  taskName: string;
  deliverables: string | null;
  chips: RoadmapChip[];
}

export interface RoadmapStage {
  stageNo: number;
  year: number;
  stageName: string;
  /** 하나마이크론만 값이 있고(원문 시급성 서술), DN오토모티브는 전부 null. */
  urgencyLevel: string | null;
  urgencyDistribution: UrgencyCounts;
  tasks: RoadmapTask[];
}

export interface UrgencyCriterion {
  level: "즉시" | "중기" | "장기";
  criteria: string;
}

export interface RoadmapResponse {
  stages: RoadmapStage[];
  /** 하나마이크론만 값이 있고, DN오토모티브는 빈 배열(화면에서 이 섹션 자체를 숨김). */
  urgencyCriteria: UrgencyCriterion[];
  /** esg_disclosure_deadline 원문 — 키는 "의무공시 적용 시점"/"고객사 해당 구간"/"실질 준비 기간"/
   * "공급망 요구"/"Scope 3 유예" 그대로. */
  disclosureDeadline: Record<string, string> | null;
  disclosureRoadmap: DisclosureRoadmap;
  /** 로드맵 마지막 단계 연도와 compute_disclosure_roadmap 계산연도가 다를 때만 채워지는 각주. */
  yearMismatchNote: string | null;
}

// ── L6 증빙 데이터룸 ──────────────────────────────────────────────────

/** 참고자료 유형별 연결 항목 수(근사치) — 라벨은 "사업보고서"/"지속가능경영보고서"/
 * "지배구조보고서"/"통합 자료"/"미분류" 고정 순서. */
export interface DocumentCount {
  label: string;
  count: number;
}

export interface DocumentCoverage {
  documentCounts: DocumentCount[];
  totalItems: number;
  unclassifiedCount: number;
  unclassifiedRate: number | null;
}

export interface EvidenceGapItem {
  code: string;
  name: string;
  evidence: EvidenceLevel;
  lostPoints: number | null;
}

// ── L7 리포트 — esg_company_profile 표지 카드(계산 없이 원본 필드 그대로) ──────

export interface CompanyProfileCard {
  stockCode: string | null;
  establishedYear: string | null;
  listingType: string | null;
  mainBusiness: string | null;
  consolidatedAssets: string | null;
  industryClassification: string | null;
  employeeCount: string | null;
}
