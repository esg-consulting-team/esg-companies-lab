import type {
  CompanyProfileCard,
  CompanyRef,
  CompanySummary,
  DocumentCoverage,
  DomainBenchmarkResponse,
  DomainDetail,
  EvidenceGapItem,
  ItemDetail,
  ItemSummary,
  ReportComparison,
  RoadmapResponse,
} from "../types";

// chat/api.ts(AI 상담 챗봇 전용 API 함수)가 재사용할 수 있도록 export한다 — 챗봇 쪽에서
// fetch 로직을 따로 구현하지 않고 이 request/post/ApiError를 그대로 쓴다.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `요청 실패 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errBody.detail ?? `요청 실패 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listCompanies: () => request<CompanyRef[]>("/api/companies"),
  getSummary: (company: string) =>
    request<CompanySummary>(`/api/companies/${encodeURIComponent(company)}/summary`),
  listItems: (company: string) =>
    request<ItemSummary[]>(`/api/companies/${encodeURIComponent(company)}/items`),
  getDomainDetail: (company: string, bucket: string) =>
    request<DomainDetail>(
      `/api/companies/${encodeURIComponent(company)}/domains/${encodeURIComponent(bucket)}`
    ),
  getItemDetail: (company: string, code: string) =>
    request<ItemDetail>(
      `/api/companies/${encodeURIComponent(company)}/items/${encodeURIComponent(code)}`
    ),
  getReportComparison: (company: string) =>
    request<ReportComparison>(`/api/companies/${encodeURIComponent(company)}/report-comparison`),
  getDomainBenchmark: (company: string) =>
    request<DomainBenchmarkResponse>(`/api/companies/${encodeURIComponent(company)}/domain-benchmark`),
  getRoadmap: (company: string) =>
    request<RoadmapResponse>(`/api/companies/${encodeURIComponent(company)}/roadmap`),
  getEvidenceDocuments: (company: string) =>
    request<DocumentCoverage>(`/api/companies/${encodeURIComponent(company)}/evidence-documents`),
  getEvidenceGaps: (company: string) =>
    request<EvidenceGapItem[]>(`/api/companies/${encodeURIComponent(company)}/evidence-gaps`),
  getProfileCard: (company: string) =>
    request<CompanyProfileCard>(`/api/companies/${encodeURIComponent(company)}/profile-card`),
};
