import { useEffect, useState } from "react";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { useCompany } from "../state/CompanyContext";

const AXES = [
  { key: "time", label: "AXIS 1 · 시점", question: "우리는 나아지고 있나" },
  { key: "peer", label: "AXIS 2 · 대상", question: "상위 기업과 무엇이 다른가" },
  { key: "target", label: "AXIS 3 · 기준", question: "만점까지 얼마나 남았나" },
];

function IntensityTable({ rows }) {
  if (rows.length === 0) {
    return <div className="empty-note">등록된 원단위 추이 데이터가 없습니다.</div>;
  }
  return (
    <table className="plain">
      <thead>
        <tr>
          <th>지표</th>
          <th className="num">2023</th>
          <th className="num">2024</th>
          <th className="num">2025</th>
          <th className="num">CAGR</th>
          <th>판정</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.metric}>
            <td>
              {r.metric}
              {r.formula_conflict && <span className="provisional-badge">산식 불일치</span>}
              {r.unit && <div style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{r.unit}</div>}
            </td>
            <td className="num mono">{r.y2023 ?? "—"}</td>
            <td className="num mono">{r.y2024 ?? "—"}</td>
            <td className="num mono">{r.y2025 ?? "—"}</td>
            <td className="num mono">{r.cagr != null ? `${(r.cagr * 100).toFixed(1)}%` : "—"}</td>
            <td style={{ color: r.verdict === "개선" ? "var(--good)" : r.verdict === "악화" ? "var(--crit)" : "var(--ink-2)" }}>
              {r.verdict || "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DivergingBars({ rows }) {
  if (rows.length === 0) {
    return <div className="empty-note">벤치마킹 평균이 등록되지 않아 갭을 계산할 수 없습니다.</div>;
  }
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.diff)), 10);
  return (
    <div>
      {rows.map((r) => {
        const pct = (Math.abs(r.diff) / maxAbs / 2) * 100;
        return (
          <div className="diverge-row" key={r.key}>
            <span>{r.label}</span>
            <div className="diverge-track">
              <div className="diverge-axis" />
              <div
                className={`diverge-fill ${r.diff < 0 ? "neg" : "pos"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="num mono" style={{ color: r.diff < 0 ? "var(--crit)" : "var(--good)" }}>
              {r.diff > 0 ? "+" : ""}
              {r.diff.toFixed(1)}%p
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Histogram({ dist }) {
  if (!dist) {
    return <div className="empty-note">업종 분포 데이터가 등록되지 않았습니다.</div>;
  }
  const max = Math.max(...dist.buckets.map((b) => b.company_count));
  return (
    <div>
      <div className="histogram">
        {dist.buckets.map((b) => {
          const isSelf = b.grade === dist.self_grade;
          return (
            <div className="histogram-col" key={b.grade}>
              <span className="histogram-count">{b.company_count}</span>
              <div
                className={`histogram-bar${isSelf ? " self" : ""}`}
                style={{ height: `${(b.company_count / max) * 100}%` }}
              />
              <span className="histogram-label">{b.grade}</span>
              {isSelf && <span className="histogram-self-label">◀ 자사</span>}
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 8 }}>
        {dist.sector_label} 업종 {dist.total_companies}개사 전수
      </div>
    </div>
  );
}

function TargetBars({ rows }) {
  return (
    <div>
      {rows.map((d) => (
        <div className="bar-row" key={d.key}>
          <span>{d.label}</span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${(d.achieved / d.max_possible) * 100}%` }}
            />
            {d.target < d.max_possible && (
              <div
                className="bar-bench-marker"
                style={{ left: `${(d.target / d.max_possible) * 100}%` }}
              />
            )}
          </div>
          <span className="num mono">
            {d.achieved.toFixed(0)} / {d.max_possible.toFixed(0)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function L4ComparisonAnalysis() {
  const { company } = useCompany();
  const [axis, setAxis] = useState("time");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company) return;
    setData(null);
    setError(null);
    api.comparison(company).then(setData).catch((err) => setError(err.message));
  }, [company]);

  if (error) return <div className="empty-state">불러오기 실패: {error}</div>;
  if (!data) return <div className="loading">불러오는 중…</div>;

  return (
    <div>
      <div className="axis-row">
        {AXES.map((a) => (
          <div
            key={a.key}
            className={`axis-card${axis === a.key ? " active" : ""}`}
            onClick={() => setAxis(a.key)}
          >
            <div className="axis-card-title">{a.label}</div>
            <div className="axis-card-question">{a.question}</div>
          </div>
        ))}
      </div>

      {axis === "time" && (
        <ExhibitCard
          number={9}
          title="환경 원단위 3개년 추이"
          subtitle="지표별로 개선/악화 방향이 다를 수 있어 함께 표기합니다. 산식 불일치 항목은 단정하지 않습니다."
          source="intensity_trends · 등록된 회사만 표시"
        >
          <IntensityTable rows={data.intensity_trend} />
        </ExhibitCard>
      )}

      {axis === "peer" && (
        <>
          <ExhibitCard
            number={10}
            title="영역별 벤치마킹 갭"
            subtitle="자사 달성률 − 벤치마킹 평균(%p). 항목 단위 벤치마킹 데이터가 없어 영역 평균 기준으로 계산합니다."
            source="esg_diagnosis + domain_benchmarks"
          >
            <DivergingBars rows={data.domain_gap} />
          </ExhibitCard>
          <ExhibitCard
            number={11}
            title="업종 등급 분포 내 위치"
            subtitle="자사가 속한 구간을 강조 표시합니다."
            source="sector_distribution_buckets · 등록된 회사만 표시"
          >
            <Histogram dist={data.sector_distribution} />
          </ExhibitCard>
        </>
      )}

      {axis === "target" && (
        <ExhibitCard
          number={12}
          title="현재 vs 만점 vs 벤치마킹 목표"
          subtitle="막대는 현재 획득 점수, 세모는 벤치마킹 평균 수준(목표선)입니다."
          source="esg_diagnosis · domain_benchmarks"
        >
          <TargetBars rows={data.domain_targets} />
        </ExhibitCard>
      )}
    </div>
  );
}
