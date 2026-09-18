import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DonutGauge } from "../components/DonutGauge";
import { useCriteriaPanel } from "../context/CriteriaPanelContext";
import {
  ExhibitCard,
  GRADE_RANK,
  GradeChangeArrow,
  GradeChip,
  MockBadge,
  StateMessage,
  formatNum,
  formatPct,
  gradeStyle,
} from "../components/common";
import type { GradeHistoryYear, IndustryProfile } from "../types";

const GRADE_TREND_LABELS: Record<Exclude<keyof GradeHistoryYear, "year" | "overall">, string> = {
  environment: "환경 E",
  social: "사회 S",
  governance: "지배구조 G",
};

/** 실제 값만으로 액션 타이틀을 구성한다 — 등급 없는 연도가 있으면 추세를 단정하지 않는다. */
function gradeTrendTitle(history: GradeHistoryYear[]): string {
  const defined = history.filter((h) => h.overall) as (GradeHistoryYear & { overall: string })[];
  if (defined.length === 0) return "등급 추이 데이터 없음";
  if (defined.length < history.length) {
    return `최근 확인된 등급 ${defined[defined.length - 1].overall} — 일부 연도 데이터 없음`;
  }
  if (new Set(defined.map((h) => h.overall)).size === 1) {
    return `${history.length}년 연속 ${defined[0].overall} — 구조적 정체`;
  }
  const firstRank = GRADE_RANK[defined[0].overall];
  const lastRank = GRADE_RANK[defined[defined.length - 1].overall];
  if (lastRank > firstRank) return "등급 개선 추세";
  if (lastRank < firstRank) return "등급 하락 추세";
  return "등급 등락 반복 — 일시적 변동";
}

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86400000);
}

function formatTrillion(won: number | null): string {
  if (won === null) return "확인 필요";
  return `${(won / 1_000_000_000_000).toFixed(1)}조원`;
}

/** "{기업명} · KOSDAQ · C2611 반도체 및 관련 부품 제조업 · 자산 2.02조원(2조원 이상)" 형식.
 * companies + company_esg_yearly 최신 연도 값을 그대로 조합 — 업종명은 확인된 코드만 붙는다. */
function formatIndustryLine(company: string, profile: IndustryProfile): string {
  const parts = [company];
  if (profile.market) parts.push(profile.market);
  if (profile.industryCode) {
    parts.push(profile.industryCode + (profile.industryName ? ` ${profile.industryName}` : ""));
  }
  if (profile.totalAssets !== null) {
    const assets = `자산 ${(profile.totalAssets / 1_000_000_000_000).toFixed(2)}조원`;
    parts.push(profile.assetTier ? `${assets}(${profile.assetTier})` : assets);
  }
  return parts.join(" · ");
}

export function L1Dashboard() {
  const { company = "" } = useParams();
  const navigate = useNavigate();
  const criteriaPanel = useCriteriaPanel();
  const { data, loading, error } = useFetch(() => api.getSummary(company), [company]);

  if (loading) return <StateMessage>불러오는 중…</StateMessage>;
  if (error || !data) return <StateMessage error>{error ?? "데이터를 불러오지 못했습니다."}</StateMessage>;

  const { assessment, officialGrade, domains, gradeHistory, evidenceCounts, urgencyCounts, lossTop5, immediateTasks, simulation, keyIssues, companyMeta } =
    { ...data, companyMeta: data.company };

  const goItem = (code: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(code)}`);

  const roadmap = companyMeta.disclosureRoadmap;
  const dday = roadmap.deadlineDate ? daysUntil(roadmap.deadlineDate) : null;

  const applicableTotalGap = urgencyCounts.즉시 + urgencyCounts.중기 + urgencyCounts.장기;

  return (
    <div className="main__grid">
      <p className="company-profile-line">{formatIndustryLine(company, companyMeta.industryProfile)}</p>

      <button className="criteria-banner" onClick={criteriaPanel.open}>
        환경·지배구조 중심 진단 · 사회(S) 제외 근거 보기
      </button>

      {/* ① D-day 밴드 */}
      <section
        className="exhibit"
        style={{ borderLeft: "3px solid var(--navy)", flexDirection: "row", alignItems: "center", gap: 16, flexWrap: "wrap" }}
      >
        {roadmap.status === "applicable" && dday !== null ? (
          <>
            <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: "var(--crit)" }}>
              D{dday >= 0 ? `-${dday}` : `+${-dday}`}
            </div>
            <div style={{ flex: 1, minWidth: 240, fontSize: 13 }}>
              착수 기한 <strong>{roadmap.deadlineDate}</strong> — 연결자산총액 {formatTrillion(roadmap.totalAssets)} 기준{" "}
              {roadmap.disclosureStartYear}년 의무공시 대상. 3개년 추세 확보를 위해 데이터 축적을 지금 시작해야 합니다.
              Scope 3 배출량은 {roadmap.scope3GraceYear}년까지 유예됩니다.
            </div>
            {companyMeta.disclosureRoadmapCaveat && (
              <div style={{ flexBasis: "100%", fontSize: 11, color: "var(--ink-3)" }}>※ {companyMeta.disclosureRoadmapCaveat}</div>
            )}
            <div style={{ flexBasis: "100%", fontSize: 11, color: "var(--ink-3)" }}>
              출처: 금융위원회 지속가능성 공시 제도화 방안(최종안), 2026.7 확정 로드맵
            </div>
          </>
        ) : roadmap.status === "not_applicable" ? (
          <div style={{ flex: 1, fontSize: 13, color: "var(--ink-2)" }}>
            연결자산총액 {formatTrillion(roadmap.totalAssets)} — 2조원 미만으로 의무공시 적용 대상 아님.
            <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
              출처: 금융위원회 지속가능성 공시 제도화 방안(최종안), 2026.7 확정 로드맵
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
            의무공시 적용시기가 아직 확정되지 않았습니다 (연결자산총액 데이터 없음).
          </div>
        )}
      </section>

      {/* ② KPI 4종 */}
      <div className="kpi-row">
        <div className="kpi-cell">
          <span className="kpi-cell__label">가채점 총점</span>
          <div className="kpi-cell__value-row">
            <DonutGauge rate={assessment.rate} size={56} />
            <span className="kpi-cell__value tabular-nums">
              {formatNum(assessment.totalScore)} / {formatNum(assessment.maxScore)}
            </span>
          </div>
          <span className="kpi-cell__sub">달성률 {formatPct(assessment.rate)} · 항목당 100점 정규화 기준</span>
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">KCGS 공식등급</span>
          <div className="kpi-cell__value-row">
            <GradeChip grade={officialGrade?.overall} />
            {gradeHistory.length >= 2 && (
              <GradeChangeArrow
                current={gradeHistory[gradeHistory.length - 1].overall}
                previous={gradeHistory[gradeHistory.length - 2].overall}
              />
            )}
            <span className="kpi-cell__sub">{officialGrade ? `${officialGrade.year}년 통합등급` : "확인 필요"}</span>
          </div>
          {!officialGrade && <MockBadge>미확보</MockBadge>}
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">근거 불충분 항목</span>
          <span className="kpi-cell__value tabular-nums">
            {evidenceCounts.불충분} / {assessment.totalItems}
          </span>
          <span className="kpi-cell__sub">부분 인정 {evidenceCounts.부분}건 포함</span>
        </div>
        <div className="kpi-cell">
          <span className="kpi-cell__label">개선 과제</span>
          <span className="kpi-cell__value tabular-nums">{applicableTotalGap} 건</span>
          <span className="kpi-cell__sub">
            즉시 {urgencyCounts.즉시} · 중기 {urgencyCounts.중기} · 장기 {urgencyCounts.장기}
          </span>
        </div>
      </div>

      {keyIssues.length > 0 && (
        <div className="key-issues-row">
          {keyIssues.map((issue) => (
            <div className="key-issue-card" key={issue.title}>
              <div className="key-issue-card__title">{issue.title}</div>
              <p className="key-issue-card__body">{issue.body}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid-2">
        {/* Exhibit 1 */}
        <ExhibitCard
          number={1}
          eyebrow="영역별 달성률"
          title={
            domains.some((d) => d.rate !== null && d.benchmarkAvg !== null && d.rate < d.benchmarkAvg - 0.3)
              ? "네 영역 모두 벤치마킹 평균에 크게 미달"
              : "영역별 달성률 현황"
          }
          eyebrowRight={<span>적용 {assessment.totalItems}개 항목</span>}
          source="esg_diagnosis (K-ESG v2.0) · 벤치마킹 평균은 샘플 값"
        >
          {domains.map((d) => (
            <div key={d.key} className={`hbar-row ${d.rate === null ? "hbar-row--disabled" : ""}`}>
              <span className="hbar-row__label">{d.label}</span>
              <div className="hbar-row__track">
                <div className="hbar-row__fill" style={{ width: `${(d.rate ?? 0) * 100}%` }} />
                {d.benchmarkAvg !== null && (
                  <div className="hbar-row__bench" style={{ left: `${d.benchmarkAvg * 100}%` }} />
                )}
              </div>
              <span className="hbar-row__meta">
                {d.rate === null ? "해당 없음" : `${formatPct(d.rate)} (${formatNum(d.score)}/${formatNum(d.max)})`}
              </span>
            </div>
          ))}
        </ExhibitCard>

        {/* Exhibit 2 */}
        <ExhibitCard
          number={2}
          eyebrow="3개년 KCGS 등급 추이"
          title={gradeTrendTitle(gradeHistory)}
          source="company_esg_yearly · 한국ESG기준원(KCGS) 공식등급"
        >
          {gradeHistory.length ? (
            <>
              <div className="grade-segments">
                {gradeHistory.map((h) => {
                  const style = gradeStyle(h.overall);
                  return style ? (
                    <div key={h.year} className="grade-segment" style={{ background: style.bg, color: style.text }}>
                      {h.year} · {h.overall}
                    </div>
                  ) : (
                    <div key={h.year} className="grade-segment grade-segment--empty">
                      {h.year} · 미평가
                    </div>
                  );
                })}
              </div>

              <div className="table-scroll" style={{ marginTop: 14 }}>
                <table className="grade-matrix">
                  <thead>
                    <tr>
                      <th>영역</th>
                      {gradeHistory.map((h) => (
                        <th key={h.year}>{h.year}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(Object.keys(GRADE_TREND_LABELS) as (keyof typeof GRADE_TREND_LABELS)[]).map((key) => (
                      <tr key={key}>
                        <td>{GRADE_TREND_LABELS[key]}</td>
                        {gradeHistory.map((h) => (
                          <td key={h.year}>
                            <GradeChip grade={h[key]} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}>
                공식 평가는 사회(S) 영역을 포함하지만, 자체 진단(K-ESG)은 정보공시·환경·지배구조(P/E/G)만 다룹니다.
              </p>
            </>
          ) : (
            <StateMessage>등급 추이 데이터가 아직 없습니다.</StateMessage>
          )}
        </ExhibitCard>
      </div>

      <div className="grid-2">
        {/* Exhibit 3 */}
        <ExhibitCard
          number={3}
          eyebrow="손실점수 Top 5"
          title="만점 대비 미획득 점수가 가장 큰 항목"
          source="esg_diagnosis · 항목당 100점 정규화 기준"
        >
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>항목코드</th>
                  <th>항목명</th>
                  <th style={{ textAlign: "right" }}>손실점수</th>
                </tr>
              </thead>
              <tbody>
                {lossTop5.map((l) => {
                  // 색만으로 심각도를 표현하지 않도록 마커 크기·글자 굵기를 손실점수에 비례시킨다.
                  const markerSize = 6 + Math.round((l.lostPoints / 100) * 6); // 6~12px
                  const severe = l.lostPoints >= 70;
                  return (
                    <tr key={l.code} className="clickable" onClick={() => goItem(l.code)}>
                      <td className="mono">{l.code}</td>
                      <td style={{ fontWeight: severe ? 700 : 400 }}>
                        <span className="severity-marker" style={{ width: markerSize, height: markerSize }} aria-hidden="true" />
                        {l.name}
                      </td>
                      <td className="num" style={{ color: "var(--crit)", fontWeight: severe ? 700 : 400 }}>
                        −{formatNum(l.lostPoints)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </ExhibitCard>

        {/* Exhibit 4 */}
        <ExhibitCard
          number={4}
          eyebrow="시급성 · 시뮬레이션"
          title={`즉시 과제 ${immediateTasks.length}건으로 달성률 ${formatPct(simulation.rateTo)} 회복 가능`}
          source="esg_diagnosis 기반 산출 · 예상치"
        >
          <div className="urgency-lanes" style={{ marginBottom: 14 }}>
            {(["즉시", "중기", "장기"] as const).map((u) => (
              <div className="urgency-lane" key={u}>
                <span className="kpi-cell__label">{u}</span>
                <span className="urgency-lane__count">{urgencyCounts[u]}</span>
                <div className="urgency-lane__bar">
                  <div
                    className={`urgency-lane__bar-fill urgency-lane__bar-fill--${u}`}
                    style={{
                      width: `${(urgencyCounts[u] / Math.max(1, urgencyCounts.즉시 + urgencyCounts.중기 + urgencyCounts.장기)) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="sim-box">
            <span className="sim-box__headline tabular-nums">
              {formatNum(simulation.from)} → {formatNum(simulation.to)} (+{formatNum(simulation.gain)})
            </span>
            <span className="sim-box__meta tabular-nums">
              달성률 {formatPct(simulation.rateFrom)} → {formatPct(simulation.rateTo)}
            </span>
            <span className="sim-box__estimate-note">예상치 — 즉시 과제 전부 착수 시 기준, 비용·기간 정보 없음</span>
          </div>
        </ExhibitCard>
      </div>

      {/* Exhibit 5 */}
      <ExhibitCard
        number={5}
        eyebrow="즉시 착수 과제"
        title={immediateTasks.length ? "가장 낮은 점수의 즉시 과제부터 착수" : "즉시 착수 과제 없음"}
        subtitle="예산·기간·담당 부서는 원본 데이터에 없어 컨설턴트 산정이 필요합니다."
        source="esg_diagnosis · urgency=즉시 기준"
      >
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>항목</th>
                <th>영역</th>
                <th>과제 (해결방안 요약)</th>
                <th style={{ textAlign: "right" }}>예상 +점</th>
              </tr>
            </thead>
            <tbody>
              {immediateTasks.map((t) => (
                <tr key={t.code} className="clickable" onClick={() => goItem(t.code)}>
                  <td className="mono">{t.code}</td>
                  <td>{t.domainLabel}</td>
                  <td>{t.name}</td>
                  <td className="num" style={{ color: "var(--good)" }}>
                    +{formatNum(t.potentialGain)}
                  </td>
                </tr>
              ))}
              {immediateTasks.length > 0 && (
                <tr className="total-row">
                  <td colSpan={3}>합계</td>
                  <td className="num">+{formatNum(simulation.gain)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </ExhibitCard>
    </div>
  );
}
