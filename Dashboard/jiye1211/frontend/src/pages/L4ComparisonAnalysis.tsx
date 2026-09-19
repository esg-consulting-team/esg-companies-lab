import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { ExhibitCard, NoData, StateMessage, formatNum } from "../components/common";
// import { EnvIntensityTrend } from "../components/EnvIntensityTrend"; // 보류 중 — README "알려진 한계" 참고
import { RadarChart } from "../components/RadarChart";
import type { DomainBenchmarkCompany, GroupedTrendGroup, PrecedentCase } from "../types";

function gapColor(gap: number): string {
  if (gap > 0) return "var(--change-up)";
  if (gap < 0) return "var(--change-down)";
  return "var(--change-flat)";
}

function fmtPct(n: number | undefined | null): string | undefined {
  if (n === undefined || n === null) return undefined;
  return `${formatNum(n, 1)}%`;
}

function fmtRange(range: [number, number] | undefined): string | undefined {
  if (!range) return undefined;
  return `${formatNum(range[0])}~${formatNum(range[1])}%`;
}

function fmtTrend(from: number | undefined, to: number | undefined): string | undefined {
  if (from === undefined || to === undefined) return undefined;
  return `${formatNum(from, 1)}% → ${formatNum(to, 1)}%`;
}

/** 그룹 하나(dependentOnReport | independentOfReport)의 자사·벤치마킹·격차를 있는 필드로만 조합한다.
 * 두 회사가 서로 다른 형식(범위 vs 연도별 값)을 쓰고, 그룹마다 있는 축도 달라 — 없는 필드는
 * "해당 데이터 없음"이 아니라 아예 그 줄을 생략한다("해당 데이터 없음"은 JSON의 실제 null 값 전용). */
function GroupStatLine({ group }: { group: GroupedTrendGroup }) {
  const self = fmtTrend(group.selfScore_2023, group.selfScore_2025) ?? fmtRange(group.selfScoreRange_2023to2025);
  const bench = group.benchmarkAvg_2025 !== undefined ? fmtPct(group.benchmarkAvg_2025) : fmtRange(group.benchmarkAvgRange_2023to2025);
  const gap = group.gap_2025;
  const gapRange = group.gapRange;
  const deltaRange = group.selfVsBenchmarkDeltaRange;

  const hasAnyStat = self || bench || gap !== undefined || gapRange || deltaRange;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {self && (
        <div style={{ fontSize: 12.5 }}>
          <span style={{ color: "var(--ink-3)" }}>자사 </span>
          <span className="tabular-nums">{self}</span>
        </div>
      )}
      {bench && (
        <div style={{ fontSize: 12.5 }}>
          <span style={{ color: "var(--ink-3)" }}>벤치마킹 평균 </span>
          <span className="tabular-nums">{bench}</span>
          {gap !== undefined && (
            <span className="tabular-nums" style={{ color: gapColor(gap), marginLeft: 8 }}>
              격차 {gap > 0 ? "+" : ""}
              {formatNum(gap, 1)}%p
            </span>
          )}
        </div>
      )}
      {gapRange && (
        <div style={{ fontSize: 12.5 }}>
          <span style={{ color: "var(--ink-3)" }}>벤치마킹 대비 </span>
          <span className="tabular-nums" style={{ color: "var(--change-down)" }}>
            격차 {gapRange[0]}~{gapRange[1]}%p
          </span>
        </div>
      )}
      {deltaRange && (
        <div style={{ fontSize: 12.5 }}>
          <span style={{ color: "var(--ink-3)" }}>벤치마킹 대비 </span>
          <span className="tabular-nums" style={{ color: "var(--change-up)" }}>
            자사 우위 +{deltaRange[0]}~{deltaRange[1]}%p
          </span>
        </div>
      )}
      {!hasAnyStat && <NoData />}
      {group.note && <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.5 }}>{group.note}</div>}
    </div>
  );
}

function PrecedentCardView({
  c,
  company,
  onGoItem,
}: {
  c: PrecedentCase;
  company: string;
  onGoItem: (code: string) => void;
}) {
  const after = c.after !== undefined ? `${formatNum(c.after)}` : c.afterRange ? `${c.afterRange[0]}~${c.afterRange[1]}` : "—";
  const gain =
    c.after !== undefined
      ? `+${formatNum(c.after - c.before)}`
      : c.afterRange
        ? `+${c.afterRange[0] - c.before}~${c.afterRange[1] - c.before}`
        : undefined;
  const period = c.beforeYear && c.afterYear ? `${c.beforeYear} → ${c.afterYear} · ` : "";

  return (
    <div className="precedent-card">
      <div className="precedent-card__head">
        <span className="precedent-card__alias">{anonymizeBenchmarkText(company, c.benchmarkAlias)}</span>
        <span className="precedent-card__duration">
          {period}
          {c.months}개월
        </span>
      </div>
      <div className="precedent-card__jump tabular-nums">
        {formatNum(c.before)} → {after}
        {gain && <span style={{ color: "var(--change-up)", marginLeft: 8, fontSize: 13 }}>({gain})</span>}
      </div>
      <div className="precedent-card__items">
        {c.itemCodes.map((code) => (
          <button key={code} className="deep-link-chip mono" onClick={() => onGoItem(code)}>
            {code}
          </button>
        ))}
      </div>
      <p className="precedent-card__note">{anonymizeBenchmarkText(company, c.note)}</p>
    </div>
  );
}

// ── Exhibit 12: 자사 vs 벤치마킹군 (company_esg_yearly · 도메인별 채점값) ──
// 벤치마킹 매핑 자체는 backend/app/benchmark_config.py에서 관리한다(회사명 기준, 실명 그대로) —
// 다만 이 Exhibit 화면 표시는 아래 BENCHMARK_ANONYMOUS_LABELS로 실명을 가려서 보여준다.
const BENCH_DOMAINS: { key: "disclosure" | "environment" | "governance"; label: string }[] = [
  { key: "disclosure", label: "정보공시" },
  { key: "environment", label: "환경" },
  { key: "governance", label: "지배구조" },
];

// 자사=--navy, 벤치마킹사는 순서대로 옅어지는 navy 계열로만 구분(무지개색 금지).
const NAVY_SHADES = ["var(--navy)", "var(--navy-2)", "var(--navy-3)", "var(--navy-4)", "var(--navy-5)"];

// 이 Exhibit 전용 익명 라벨 — backend/app/benchmark_config.py BENCHMARK_MAP의 리스트 순서에
// 기대지 않고, 회사별 실명→익명 라벨을 여기 명시적으로 고정한다. 범례·막대 라벨·툴팁 어디에도
// 실명이 노출되지 않도록 반드시 이 매핑을 거쳐서만 표시한다.
// L7Report.tsx의 "④ 벤치마킹 비교" 표도 같은 매핑이 필요해서 export한다 — L7에 따로 만들지
// 않고 여기서 가져다 쓰게 해서, 매핑이 두 곳에서 따로 어긋나는 걸 막는다.
export const BENCHMARK_ANONYMOUS_LABELS: Record<string, Record<string, string>> = {
  하나마이크론: { SK하이닉스: "A사", 삼성전자: "B사", 삼성전기: "C사" },
  DN오토모티브: { HD현대일렉트릭: "A사", 엘에스일렉트릭: "B사", SK아이이테크놀로지: "C사", 대한전선: "D사" },
};

export function anonymizeBenchmarkPeer(clientCompany: string, peerRealName: string): string {
  return BENCHMARK_ANONYMOUS_LABELS[clientCompany]?.[peerRealName] ?? peerRealName;
}

/** 벤치마킹사를 익명 라벨(A사→B사→…) 순으로 정렬한다 — API 응답 순서와 무관하게 항상 같은 순서. L4·L7 공용. */
export function sortPeersByAnonymousLabel<T extends { company: string }>(clientCompany: string, peers: T[]): T[] {
  return [...peers].sort((a, b) =>
    anonymizeBenchmarkPeer(clientCompany, a.company).localeCompare(anonymizeBenchmarkPeer(clientCompany, b.company))
  );
}

/** benchmarkAlias처럼 실명이 문장 중간에 섞여 나오는 문자열용 — 문장 구조는 그대로 두고
 * 알고 있는 실명 부분만 치환한다(예: "벤치마킹 (대한전선 사례)" → "벤치마킹 (D사 사례)"). */
function anonymizeBenchmarkText(clientCompany: string, text: string): string {
  const map = BENCHMARK_ANONYMOUS_LABELS[clientCompany];
  if (!map) return text;
  let result = text;
  for (const [real, anon] of Object.entries(map)) {
    result = result.split(real).join(anon);
  }
  return result;
}

function SelfVsBenchmarkGroupExhibit({ company }: { company: string }) {
  const { data, loading, error } = useFetch(() => api.getDomainBenchmark(company), [company]);
  const hasData = !!data?.self && (data?.peers.length ?? 0) > 0;
  // 익명 라벨(A사→B사→…) 순으로 정렬해 API 응답 순서와 무관하게 항상 같은 순서로 보여준다.
  const peers = sortPeersByAnonymousLabel(company, data?.peers ?? []);

  return (
    <ExhibitCard
      number={12}
      eyebrow="자사 vs 벤치마킹군"
      title={hasData ? "영역별 통합 채점 비교" : "벤치마킹 데이터 없음"}
      subtitle="정보공시·환경·지배구조만 비교"
      source="벤치마킹사 개별 채점값(팀 채점표 기준) · 벤치마킹사는 익명 처리됨"
    >
      {loading && <StateMessage>불러오는 중…</StateMessage>}
      {error && <StateMessage error>{error}</StateMessage>}
      {data && !hasData && <NoData>해당 데이터 없음</NoData>}
      {data && hasData && (
        <>
          <RadarChart
            axes={BENCH_DOMAINS.map((d) => ({ key: d.key, label: d.label }))}
            series={[
              {
                label: `자사 · ${data.self!.company}`,
                color: "var(--navy)",
                emphasize: true,
                values: data.self! as unknown as Record<string, number | null>,
              },
              ...peers.map((p, i) => ({
                label: anonymizeBenchmarkPeer(company, p.company),
                color: NAVY_SHADES[i + 1] ?? "var(--navy-5)",
                values: p as unknown as Record<string, number | null>,
              })),
            ]}
          />
          {BENCH_DOMAINS.map(({ key, label }) => {
            const rows: (DomainBenchmarkCompany & { isSelf: boolean })[] = [
              { ...data.self!, isSelf: true },
              ...peers.map((p) => ({ ...p, isSelf: false })),
            ];
            return (
              <div className="bench-group" key={key}>
                <div className="bench-group__label">{label}</div>
                {rows.map((r, i) => {
                  const value = r[key];
                  return (
                    <div className="bench-row" key={r.company}>
                      <span className={`bench-row__label ${r.isSelf ? "bench-row__label--self" : ""}`}>
                        {r.isSelf ? `자사 · ${r.company}` : anonymizeBenchmarkPeer(company, r.company)}
                      </span>
                      <div className="bench-row__track">
                        {value !== null && (
                          <div className="bench-row__fill" style={{
                              width: `${value}%`,
                              background: NAVY_SHADES[i] ?? "var(--navy-5)",
                              // 가장 옅은 색은 트랙 배경(--navy-5)과 같아 막대가 안 보이므로 윤곽선을 준다.
                              boxShadow: (NAVY_SHADES[i] ?? "var(--navy-5)") === "var(--navy-5)" ? "inset 0 0 0 1px var(--navy-4)" : undefined,
                            }} />
                        )}
                      </div>
                      <span className="bench-row__meta">{value !== null ? `${formatNum(value, 1)}%` : <NoData />}</span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </>
      )}
    </ExhibitCard>
  );
}

export function L4ComparisonAnalysis() {
  const { company = "" } = useParams();
  const navigate = useNavigate();
  const { data, loading, error } = useFetch(() => api.getReportComparison(company), [company]);

  const goItem = (code: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(code)}`);

  if (loading) return <StateMessage>불러오는 중…</StateMessage>;
  if (error || !data) return <StateMessage error>{error ?? "비교 데이터를 불러오지 못했습니다."}</StateMessage>;

  const breakdownLine = Object.entries(data.itemBreakdown)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${k} ${v}`)
    .join(" · ");

  const zeroItems = data.structuralZeroItems_3yearConsecutive;
  const zeroPreview = zeroItems.slice(0, 4).join(", ") + (zeroItems.length > 4 ? ` 외 ${zeroItems.length - 4}건` : "");

  return (
    <div className="main__grid">
      <div className="kpi-row">
        <div className="kpi-cell">
          <span className="kpi-cell__label">적용 항목</span>
          <span className="kpi-cell__value tabular-nums">{data.applicableItems}개</span>
          <span className="kpi-cell__sub">{breakdownLine}</span>
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">벤치마킹 대상</span>
          <span className="kpi-cell__value tabular-nums">{data.benchmarkCompanyCount}개사</span>
          <span className="kpi-cell__sub">{data.benchmarkAliases.join(" · ")}</span>
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">자사 총점 vs 벤치마킹</span>
          <span className="kpi-cell__value tabular-nums">{formatNum(data.totalScore.self, 1)}%</span>
          <span className="kpi-cell__sub">
            벤치마킹 평균 {formatNum(data.totalScore.benchmarkAvg, 1)}% ·{" "}
            <span style={{ color: gapColor(data.totalScore.gap) }}>격차 {formatNum(data.totalScore.gap, 1)}%p</span>
          </span>
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">3개년 연속 0점</span>
          <span className="kpi-cell__value tabular-nums">{zeroItems.length}개</span>
          <span className="kpi-cell__sub mono" style={{ fontWeight: zeroItems.length ? 700 : 400 }}>
            {zeroItems.length ? (
              <>
                <span className="severity-marker" style={{ width: 8, height: 8 }} aria-hidden="true" />
                {zeroPreview}
              </>
            ) : (
              "해당 없음"
            )}
          </span>
        </div>
      </div>

      {data.benchmarkMissingDomains.length > 0 && (
        <p style={{ fontSize: 12, color: "var(--ink-3)" }}>
          {data.benchmarkMissingDomains.map((m) => `※ ${m.company} — ${m.note}`).join(" ")}
        </p>
      )}

      <ExhibitCard
        number={9}
        eyebrow="그룹비교"
        title="지속가능경영보고서 의존도에 따른 개선 격차"
        subtitle="보고서 의존 항목: 지속가능경영보고서 기재 수준에 좌우되는 항목 · 보고서 무관 항목: 그 외 항목"
      >
        <div className="grid-2">
          <div>
            <div className="upper-label" style={{ marginBottom: 6 }}>
              보고서 의존 항목 ({data.groupedScoreTrend.dependentOnReport.itemCount}개)
            </div>
            <GroupStatLine group={data.groupedScoreTrend.dependentOnReport} />
          </div>
          <div>
            <div className="upper-label" style={{ marginBottom: 6 }}>
              보고서 무관 항목 ({data.groupedScoreTrend.independentOfReport.itemCount}개)
            </div>
            <GroupStatLine group={data.groupedScoreTrend.independentOfReport} />
          </div>
        </div>
        {data.groupedScoreTrend.overallAvgTrend && (
          <p style={{ fontSize: 12.5, marginTop: 12, color: "var(--ink-2)" }}>
            전사 평균 {data.groupedScoreTrend.overallAvgTrend["2023"]}% → {data.groupedScoreTrend.overallAvgTrend["2025"]}%
            {data.groupedScoreTrend.overallAvgTrend.note ? ` — ${data.groupedScoreTrend.overallAvgTrend.note}` : ""}
          </p>
        )}
        {data.groupedScoreTrend.note_dataConfidence && (
          <p style={{ fontSize: 11, marginTop: 8, color: "var(--ink-3)" }}>{data.groupedScoreTrend.note_dataConfidence}</p>
        )}
      </ExhibitCard>

      {/* Exhibit 10 · KCGS 등급 상관도 — 화면에서 제거(하나마이크론 전용 기능이라 DN오토모티브는
          어차피 note_kcgsCorrelation만 보였음). 완전 삭제하지 않고 주석 처리만 함 — 부활 요청 대비.
      <ExhibitCard
        number={10}
        eyebrow="KCGS 등급 상관도"
        title={
          data.kcgsCorrelation
            ? "격차가 큰 항목일수록 KCGS 등급과의 상관관계도 뚜렷하다"
            : "이 회사는 KCGS 등급 상관도 분석 데이터가 없음"
        }
        source="Spearman ρ"
      >
        {data.kcgsCorrelation ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>항목코드</th>
                  <th>항목명</th>
                  <th>자사</th>
                  <th>벤치마킹 평균</th>
                  <th>격차</th>
                  <th>상관계수(ρ)</th>
                </tr>
              </thead>
              <tbody>
                {data.kcgsCorrelation.map((row) => (
                  <tr key={row.itemCode} className="clickable" onClick={() => goItem(row.itemCode)}>
                    <td className="mono">{row.itemCode}</td>
                    <td>{row.itemName}</td>
                    <td className="num">{formatNum(row.self, 1)}</td>
                    <td className="num">{formatNum(row.benchmarkAvg, 1)}</td>
                    <td className="num" style={{ color: gapColor(row.gap) }}>
                      {formatNum(row.gap, 1)}
                    </td>
                    <td className="num">
                      {row.rho !== null ? (
                        formatNum(row.rho, 2)
                      ) : (
                        <span style={{ color: "var(--ink-3)" }}>{row.rhoNote ?? "해당 데이터 없음"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <NoData>{data.note_kcgsCorrelation ?? "해당 데이터 없음"}</NoData>
        )}
      </ExhibitCard>
      */}

      <ExhibitCard
        number={11}
        eyebrow="선례 카드"
        title="벤치마킹 기업의 실제 도약 사례"
        subtitle="같은 항목에서 벤치마킹 기업이 점수를 끌어올린 방법과 소요 기간"
      >
        {data.precedentCases.length ? (
          data.precedentCases.map((c, i) => <PrecedentCardView key={i} c={c} company={company} onGoItem={goItem} />)
        ) : (
          <NoData />
        )}
      </ExhibitCard>

      <SelfVsBenchmarkGroupExhibit company={company} />

      {/* 환경 원단위 3개년 추이(Exhibit 13) — 자동채점/수기 근거 충돌로 보류 중. 재활성화: 위 import 주석 해제 후 이 줄 복구.
      <EnvIntensityTrend company={company} />
      */}
    </div>
  );
}
