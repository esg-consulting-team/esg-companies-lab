import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { ExhibitCard, NoData, StateMessage, formatNum } from "../components/common";
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

function PrecedentCardView({ c, onGoItem }: { c: PrecedentCase; onGoItem: (code: string) => void }) {
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
        <span className="precedent-card__alias">{c.benchmarkAlias}</span>
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
      <p className="precedent-card__note">{c.note}</p>
    </div>
  );
}

// ── Exhibit 12: 자사 vs 벤치마킹군 (company_esg_yearly · 도메인별 채점값) ──
// 벤치마킹 매핑 자체는 backend/app/benchmark_config.py에서 관리한다(회사명 기준, 실명 그대로).
const BENCH_DOMAINS: { key: "disclosure" | "environment" | "governance"; label: string }[] = [
  { key: "disclosure", label: "정보공시" },
  { key: "environment", label: "환경" },
  { key: "governance", label: "지배구조" },
];

// 자사=--navy, 벤치마킹사는 순서대로 옅어지는 navy 계열로만 구분(무지개색 금지).
const NAVY_SHADES = ["var(--navy)", "var(--navy-2)", "var(--navy-3)", "var(--navy-4)", "var(--navy-5)"];

function SelfVsBenchmarkGroupExhibit({ company }: { company: string }) {
  const { data, loading, error } = useFetch(() => api.getDomainBenchmark(company), [company]);
  // 반도체특화 도메인은 company_esg_yearly에 컬럼이 없어 별도 소스(report_extracted_data.json)에서
  // 가져온다 — 이 필드가 있는 회사(현재는 하나마이크론)에서만 하단 미니 표가 나타난다.
  const { data: reportData } = useFetch(() => api.getReportComparison(company), [company]);
  const hasData = !!data?.self && (data?.peers.length ?? 0) > 0;
  const semiconductorScores = reportData?.domainScoresByCompany?.["반도체특화"];

  return (
    <ExhibitCard
      number={12}
      eyebrow="자사 vs 벤치마킹군"
      title={hasData ? "벤치마킹군과 도메인별 채점값을 나란히 비교" : "벤치마킹 데이터 없음"}
      subtitle="정보공시·환경·지배구조만 비교합니다 — company_esg_yearly에는 업종특화/반도체특화 도메인의 별도 채점 컬럼이 없어 항목 단위 비교와 함께 제외했습니다."
      source="company_esg_yearly · 벤치마킹사 개별 채점값(팀 채점표 기준)"
    >
      {loading && <StateMessage>불러오는 중…</StateMessage>}
      {error && <StateMessage error>{error}</StateMessage>}
      {data && !hasData && <NoData>해당 데이터 없음</NoData>}
      {data && hasData && (
        <>
          {BENCH_DOMAINS.map(({ key, label }) => {
            const rows: (DomainBenchmarkCompany & { isSelf: boolean })[] = [
              { ...data.self!, isSelf: true },
              ...data.peers.map((p) => ({ ...p, isSelf: false })),
            ];
            return (
              <div className="bench-group" key={key}>
                <div className="bench-group__label">{label}</div>
                {rows.map((r, i) => {
                  const value = r[key];
                  return (
                    <div className="bench-row" key={r.company}>
                      <span className={`bench-row__label ${r.isSelf ? "bench-row__label--self" : ""}`}>
                        {r.isSelf ? `자사 · ${r.company}` : r.company}
                      </span>
                      <div className="bench-row__track">
                        {value !== null && (
                          <div className="bench-row__fill" style={{ width: `${value}%`, background: NAVY_SHADES[i] ?? "var(--navy-5)" }} />
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

      {semiconductorScores && (
        <>
          <hr className="exhibit__rule" />
          <div className="upper-label" style={{ marginBottom: 8 }}>
            반도체특화 (보고서 원문 기준)
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>대상</th>
                <th className="num">채점값</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(semiconductorScores).map(([label, value]) => (
                <tr key={label}>
                  <td>{label === company ? `자사 · ${company}` : label}</td>
                  <td className="num">{value !== null ? `${formatNum(value, 1)}%` : "미채점"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 8 }}>
            반도체특화 벤치마킹은 보고서 원문의 익명 라벨(A/B/C)이며, 위 실명 벤치마킹사와 순서가 대응한다고 확인되지 않았으므로 별도로 표시함
          </p>
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
        title="지속가능경영보고서 의존 여부에 따라 개선 속도가 갈린다"
        subtitle="보고서 의존 항목: 지속가능경영보고서 기재 수준에 좌우되는 항목 · 보고서 무관 항목: 그 외 항목"
        source="report_extracted_data.json · groupedScoreTrend"
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

      <ExhibitCard
        number={10}
        eyebrow="KCGS 등급 상관도"
        title={
          data.kcgsCorrelation
            ? "격차가 큰 항목일수록 KCGS 등급과의 상관관계도 뚜렷하다"
            : "이 회사는 KCGS 등급 상관도 분석 데이터가 없음"
        }
        source="report_extracted_data.json · kcgsCorrelation (Spearman ρ)"
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

      <ExhibitCard
        number={11}
        eyebrow="선례 카드"
        title="벤치마킹 기업의 실제 도약 사례"
        subtitle="같은 항목에서 벤치마킹 기업이 점수를 끌어올린 방법과 소요 기간"
        source="report_extracted_data.json · precedentCases"
      >
        {data.precedentCases.length ? (
          data.precedentCases.map((c, i) => <PrecedentCardView key={i} c={c} onGoItem={goItem} />)
        ) : (
          <NoData />
        )}
      </ExhibitCard>

      <SelfVsBenchmarkGroupExhibit company={company} />
    </div>
  );
}
