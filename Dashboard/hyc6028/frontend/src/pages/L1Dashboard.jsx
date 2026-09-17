import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { GradeChip, UrgencyTag } from "../components/Badges";
import DonutGauge from "../components/DonutGauge";
import EsgMiniChips from "../components/EsgMiniChips";
import UrgencyDonut from "../components/UrgencyDonut";
import { useCompany } from "../state/CompanyContext";

function DdayBand({ dday }) {
  if (!dday || !dday.deadline_date) {
    return (
      <div className="dday-band">
        <div>
          <div className="upper-label" style={{ marginBottom: 4 }}>
            의무공시 D-day
          </div>
          <div style={{ fontSize: 13 }}>
            연결자산총액 기준 적용 구간 데이터가 등록되지 않아 착수 기한을 계산할 수 없습니다.{" "}
            <span className="provisional-badge">적용 차수 확정 필요</span>
          </div>
        </div>
      </div>
    );
  }
  const days = dday.days_left;
  return (
    <div className="dday-band">
      <div className="dday-value mono">{days >= 0 ? `D-${days}` : `D+${-days}`}</div>
      <div style={{ fontSize: 13 }}>
        착수 기한 <strong>{dday.deadline_date}</strong> — 연결자산 기준 {dday.tier}차 구간,{" "}
        {dday.apply_year}년 공시 대상. {dday.prep_years}개년 추세 확보를 위해 지금 데이터 축적을
        시작해야 합니다.
        <div style={{ marginTop: 6, fontSize: 11.5, color: "var(--ink-2)" }}>{dday.tier_text}</div>
      </div>
    </div>
  );
}

function DomainBars({ domains }) {
  return (
    <div>
      {domains.map((d) => (
        <div className="bar-row" key={d.key}>
          <span>{d.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${d.achievement_rate * 100}%` }} />
            {d.benchmark_avg != null && (
              <div className="bar-bench-marker" style={{ left: `${d.benchmark_avg * 100}%` }} />
            )}
          </div>
          <span className="num mono">
            {(d.achievement_rate * 100).toFixed(1)}% ({d.items}개)
          </span>
        </div>
      ))}
    </div>
  );
}

function GradeMatrix({ gradeTrend }) {
  if (!gradeTrend || gradeTrend.length === 0) {
    return <div className="empty-state">등급 추이 데이터가 없습니다.</div>;
  }
  const years = Array.from(new Set(gradeTrend.flatMap((row) => Object.keys(row.grades)))).sort();
  return (
    <table className="plain grade-matrix">
      <thead>
        <tr>
          <th rowSpan={2}>기업</th>
          {years.map((y) => (
            <th key={y} className="num year-header" colSpan={4}>
              {y}
            </th>
          ))}
        </tr>
        <tr>
          {years.map((y) => (
            <Fragment key={y}>
              <th className="num sub-overall">종합</th>
              <th className="num sub-esg">E</th>
              <th className="num sub-esg">S</th>
              <th className="num sub-esg">G</th>
            </Fragment>
          ))}
        </tr>
      </thead>
      <tbody>
        {gradeTrend.map((row) => (
          <tr key={row.alias}>
            <td style={{ fontWeight: row.self_company ? 500 : 300 }}>{row.alias}</td>
            {years.map((y) => {
              const g = row.grades[y] || {};
              return (
                <Fragment key={y}>
                  <td className="num cell-overall">
                    <GradeChip grade={g.overall} />
                  </td>
                  <td className="num cell-esg mono">{g.e || "–"}</td>
                  <td className="num cell-esg cell-s mono">{g.s || "–"}</td>
                  <td className="num cell-esg mono">{g.g || "–"}</td>
                </Fragment>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function L1Dashboard() {
  const { company } = useCompany();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!company) return;
    setData(null);
    setError(null);
    api.summary(company).then(setData).catch((err) => setError(err.message));
  }, [company]);

  if (error) return <div className="empty-state">불러오기 실패: {error}</div>;
  if (!data) return <div className="loading">불러오는 중…</div>;

  const {
    kpi,
    domains,
    grade_trend,
    official_grade,
    gap_top,
    urgency_counts,
    immediate_tasks,
    dday,
  } = data;
  const totalTasks = urgency_counts.즉시 + urgency_counts.중기 + urgency_counts.장기;
  const latestYear = Math.max(
    ...grade_trend.flatMap((row) => Object.keys(row.grades).map(Number)),
    0
  );
  const selfLatest =
    grade_trend.find((r) => r.self_company)?.grades?.[String(latestYear)] || {};
  const immediateTotal = immediate_tasks.reduce((s, t) => s + t.lost_points, 0);

  return (
    <div>
      <DdayBand dday={dday} />

      <div className="kpi-row">
        <div className="kpi-cell">
          <div className="kpi-label">가채점 총점</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <DonutGauge value={kpi.achievement_rate} />
            <div>
              <div className="kpi-value serif num">{kpi.total_score.toFixed(0)}</div>
              <div className="kpi-sub num">/ {kpi.max_score.toFixed(0)}</div>
            </div>
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">KCGS 공식등급</div>
          <div className="kpi-value">
            <GradeChip grade={official_grade} />
            <EsgMiniChips e={selfLatest.e} s={selfLatest.s} g={selfLatest.g} />
          </div>
          <div className="kpi-sub">{latestYear || "—"}년 기준</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">근거 불충분 항목</div>
          <div className="kpi-value serif num">
            {kpi.insufficient_evidence_items} / {kpi.applicable_items}
          </div>
          <div className="kpi-sub">증빙 보완으로 회복 가능 {kpi.recoverable_by_evidence}건</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">개선 과제</div>
          <div className="kpi-value serif num">{totalTasks}건</div>
          <div className="kpi-sub">
            즉시 {urgency_counts.즉시} · 중기 {urgency_counts.중기} · 장기 {urgency_counts.장기}
          </div>
        </div>
      </div>

      <div className="exhibit-grid-2">
        <ExhibitCard
          number={1}
          title="영역별 달성률"
          subtitle="자사 진행 막대와 벤치마킹 평균(▼)을 비교합니다."
          source="2026년 채점 결과 기준 영역별 달성률 · 벤치마킹 평균은 등록된 경우만 표시"
        >
          <DomainBars domains={domains} />
        </ExhibitCard>

        <ExhibitCard
          number={2}
          title={grade_trend.length > 0 ? "KCGS 등급 추이" : "KCGS 등급 데이터 없음"}
          subtitle="연도별 종합등급과 E/S/G 세부등급을 함께 표기합니다."
          source="한국ESG기준원(KCGS) 등급 결과 · 벤치마킹 기업명은 비공개 처리"
        >
          <GradeMatrix gradeTrend={grade_trend} />
        </ExhibitCard>
      </div>

      <ExhibitCard
        number={3}
        title="손실점수 Top 5"
        subtitle="만점(100) 대비 미획득 점수가 큰 순서입니다. 클릭 시 항목 상세로 이동합니다."
        source="2026년 채점 결과 기준 실시간 계산"
      >
        <table className="plain">
          <thead>
            <tr>
              <th>항목코드</th>
              <th>항목명</th>
              <th className="num">손실점수</th>
            </tr>
          </thead>
          <tbody>
            {gap_top.map((g) => (
              <tr
                key={g.item_code}
                data-testid="gap-top-row"
                onClick={() => navigate(`/l3?item=${g.item_code}`)}
              >
                <td className="mono">{g.item_code}</td>
                <td>{g.item_name}</td>
                <td className="num mono" style={{ color: "var(--crit)" }}>
                  -{g.lost_points.toFixed(0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ExhibitCard>

      <ExhibitCard
        number={4}
        title="시급성 분포"
        subtitle="전체 개선 과제를 즉시/중기/장기로 분류한 비율입니다."
        source="2026년 채점 결과 기준 항목별 시급성 집계"
      >
        <UrgencyDonut counts={urgency_counts} />
      </ExhibitCard>

      <ExhibitCard
        number={5}
        title="즉시 착수 과제"
        subtitle={`시급성 '즉시'로 분류된 전체 ${immediate_tasks.length}건입니다. 예상 회복점수는 만점 대비 손실분입니다.`}
        source="2026년 채점 결과의 해결방안 필드에서 자동 추출 · 예상치"
      >
        <div className="exhibit-scroll">
          <table className="plain">
            <thead>
              <tr>
                <th>항목</th>
                <th>개선 방향</th>
                <th className="num">예상 +점</th>
              </tr>
            </thead>
            <tbody>
              {immediate_tasks.map((t) => (
                <tr key={t.item_code} onClick={() => navigate(`/l3?item=${t.item_code}`)}>
                  <td>
                    <span className="mono">{t.item_code}</span>
                    <br />
                    <UrgencyTag urgency={t.urgency} /> {t.item_name}
                  </td>
                  <td style={{ fontSize: 12 }}>{t.direction || "—"}</td>
                  <td className="num mono" style={{ color: "var(--good)" }}>
                    +{t.lost_points.toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>합계</td>
                <td className="num mono" style={{ color: "var(--good)" }}>
                  +{immediateTotal.toFixed(0)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </ExhibitCard>
    </div>
  );
}
