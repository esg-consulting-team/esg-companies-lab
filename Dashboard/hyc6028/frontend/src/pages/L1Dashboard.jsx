import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { GradeChip, UrgencyTag } from "../components/Badges";
import { useCompany } from "../state/CompanyContext";

function DdayBand({ meta }) {
  if (!meta.phase_confirmed || !meta.deadline_date) {
    return (
      <div className="dday-band">
        <div>
          <div className="upper-label" style={{ marginBottom: 4 }}>
            의무공시 D-day
          </div>
          <div style={{ fontSize: 13 }}>
            연결자산총액이 확정되지 않아 적용 차수를 계산할 수 없습니다.{" "}
            <span className="provisional-badge">적용 차수 확정 필요</span>
          </div>
        </div>
      </div>
    );
  }
  const days = Math.ceil((new Date(meta.deadline_date) - new Date()) / 86400000);
  return (
    <div className="dday-band">
      <div className="dday-value mono">{days >= 0 ? `D-${days}` : `D+${-days}`}</div>
      <div style={{ fontSize: 13 }}>
        착수 기한 <strong>{meta.deadline_date}</strong> — {meta.disclosure_phase}차 대상. 3개년 추세 확보를
        위해 데이터 축적을 지금 시작해야 합니다.
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
  const years = Array.from(
    new Set(gradeTrend.flatMap((row) => Object.keys(row.grades)))
  ).sort();
  return (
    <table className="plain">
      <thead>
        <tr>
          <th>기업</th>
          {years.map((y) => (
            <th key={y} className="num">
              {y}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {gradeTrend.map((row) => (
          <tr key={row.alias}>
            <td style={{ fontWeight: row.self_company ? 500 : 300 }}>{row.alias}</td>
            {years.map((y) => (
              <td key={y} className="num">
                <GradeChip grade={row.grades[y]} />
              </td>
            ))}
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

  const { kpi, domains, grade_trend, official_grade, gap_top, urgency_counts, immediate_tasks, company: meta } =
    data;
  const totalTasks = urgency_counts.즉시 + urgency_counts.중기 + urgency_counts.장기;

  return (
    <div>
      <DdayBand meta={meta} />

      <div className="kpi-row">
        <div className="kpi-cell">
          <div className="kpi-label">가채점 총점</div>
          <div className="kpi-value serif num">{(kpi.achievement_rate * 100).toFixed(1)}%</div>
          <div className="kpi-sub num">
            {kpi.total_score.toFixed(0)} / {kpi.max_score.toFixed(0)}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">KCGS 공식등급</div>
          <div className="kpi-value">
            <GradeChip grade={official_grade} />
          </div>
          <div className="kpi-sub">2025년 통합등급 (미보유 시 &quot;미확인&quot;)</div>
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
          source="esg_diagnosis (K-ESG v2.0) · 벤치마킹 평균은 별도 등록된 값이 있을 때만 표시"
        >
          <DomainBars domains={domains} />
        </ExhibitCard>

        <ExhibitCard
          number={2}
          title={
            grade_trend.length > 0
              ? "KCGS 등급 추이"
              : "KCGS 등급 데이터 없음"
          }
          subtitle="등급은 순서형이라 칩 매트릭스로 표기합니다."
          source="한국ESG기준원(KCGS) · 벤치마킹 기업명은 비공개 처리"
        >
          <GradeMatrix gradeTrend={grade_trend} />
        </ExhibitCard>
      </div>

      <ExhibitCard
        number={3}
        title="손실점수 Top 5"
        subtitle="만점(100) 대비 미획득 점수가 큰 순서입니다. 클릭 시 항목 상세로 이동합니다."
        source="esg_diagnosis 자사취득점수 기준 실시간 계산"
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
              <tr key={g.item_code} onClick={() => navigate(`/l3?item=${g.item_code}`)}>
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
        title="즉시 착수 과제"
        subtitle="시급성 '즉시'로 분류된 항목 중 손실점수가 큰 순서 5건입니다. 예상 회복점수는 만점 대비 손실분입니다."
        source="esg_diagnosis 해결방안 필드에서 자동 추출 · 예상치"
      >
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
        </table>
      </ExhibitCard>
    </div>
  );
}
