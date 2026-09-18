import { useEffect, useState } from "react";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
} from "recharts";
import { api } from "../api/client";
import { GradeChip } from "../components/Badges";
import ExhibitCard from "../components/ExhibitCard";
import Tooltip from "../components/Tooltip";
import { useCompany } from "../state/CompanyContext";

const AXES = [
  { key: "time", label: "AXIS 1 · 시점", question: "우리는 나아지고 있나" },
  { key: "peer", label: "AXIS 2 · 대상", question: "상위 기업과 무엇이 다른가" },
  { key: "target", label: "AXIS 3 · 기준", question: "만점까지 얼마나 남았나" },
];

const RADAR_DOMAIN_LABELS = {
  disclosure: "정보공시",
  environment: "환경",
  governance: "지배구조",
  sector: "업종특화",
};

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

function BenchmarkCards({ company }) {
  const [cards, setCards] = useState(null);
  useEffect(() => {
    if (!company) return;
    setCards(null);
    api.benchmarkCompanies(company).then(setCards).catch(() => setCards([]));
  }, [company]);

  if (!cards) return <div className="loading">불러오는 중…</div>;
  if (cards.length === 0) {
    return <div className="empty-note">등록된 벤치마킹 기업 정보가 없습니다.</div>;
  }
  return (
    <div className="benchmark-card-grid">
      {cards.map((c) => (
        <Tooltip key={c.benchmark_label} content={c.rationale}>
          <div className="benchmark-card">
            <div className="benchmark-card-label">벤치마킹 {c.benchmark_label}</div>
            <div className="benchmark-card-industry">{c.industry}</div>
            <GradeChip grade={c.grade_2025} />
          </div>
        </Tooltip>
      ))}
    </div>
  );
}

function RadarExhibit() {
  const [radarData, setRadarData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.summary("하나마이크론"), api.summary("DN오토모티브")])
      .then(([hana, dn]) => {
        const rateByKey = (s) => Object.fromEntries(s.domains.map((d) => [d.key, d.achievement_rate]));
        const h = rateByKey(hana);
        const d = rateByKey(dn);
        const rows = ["disclosure", "environment", "governance", "sector"].map((k) => ({
          domain: RADAR_DOMAIN_LABELS[k],
          하나마이크론: Math.round((h[k] || 0) * 100),
          DN오토모티브: Math.round((d[k] || 0) * 100),
        }));
        rows.push({ domain: "사회(진단 예정)", 하나마이크론: 0, DN오토모티브: 0 });
        setRadarData(rows);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <ExhibitCard
      number={13}
      title="영역별 달성률 레이더 — 두 기업 비교"
      subtitle="사회(S) 영역은 이번 진단 범위(E/G) 밖이라 0%로 표시됩니다."
      source="2026년 채점 결과 기준 하나마이크론·DN오토모티브 비교"
    >
      {error && <div className="empty-note">불러오기 실패: {error}</div>}
      {!radarData && !error && <div className="loading">불러오는 중…</div>}
      {radarData && (
        <RadarChart width={420} height={320} data={radarData} outerRadius="75%">
          <PolarGrid stroke="var(--rule)" />
          <PolarAngleAxis dataKey="domain" tick={{ fontSize: 11, fill: "var(--ink-2)" }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9, fill: "var(--ink-3)" }} />
          <Radar
            name="하나마이크론"
            dataKey="하나마이크론"
            stroke="var(--navy)"
            fill="var(--navy)"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
          <Radar
            name="DN오토모티브"
            dataKey="DN오토모티브"
            stroke="var(--crit)"
            fill="var(--crit)"
            fillOpacity={0.15}
            isAnimationActive={false}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </RadarChart>
      )}
    </ExhibitCard>
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
          source="2026년 환경 원단위 집계 자료 · 등록된 회사만 표시"
        >
          <IntensityTable rows={data.intensity_trend} />
        </ExhibitCard>
      )}

      {axis === "peer" && (
        <>
          <ExhibitCard
            number={10}
            title="벤치마킹 기업 개요"
            subtitle="카드에 마우스를 올리면 선정 사유를 볼 수 있습니다."
            source="컨설팅보고서 원문에서 추출한 벤치마킹 기업 정보 · 등록된 회사만 표시"
          >
            <BenchmarkCards company={company} />
          </ExhibitCard>
          <ExhibitCard
            number={11}
            title="영역별 벤치마킹 갭"
            subtitle="자사 달성률 − 벤치마킹 평균(%p). 항목 단위 벤치마킹 데이터가 없어 영역 평균 기준으로 계산합니다."
            source="2026년 채점 결과와 영역별 벤치마킹 평균 비교"
          >
            <DivergingBars rows={data.domain_gap} />
          </ExhibitCard>
          <ExhibitCard
            number={12}
            title="업종 등급 분포 내 위치"
            subtitle="자사가 속한 구간을 강조 표시합니다."
            source="한국ESG기준원(KCGS) 업종 등급 분포 · 등록된 회사만 표시"
          >
            <Histogram dist={data.sector_distribution} />
          </ExhibitCard>
          <RadarExhibit />
        </>
      )}

      {axis === "target" && (
        <ExhibitCard
          number={14}
          title="현재 vs 만점 vs 벤치마킹 목표"
          subtitle="막대는 현재 획득 점수, 세모는 벤치마킹 평균 수준(목표선)입니다."
          source="2026년 채점 결과와 영역별 벤치마킹 평균 비교"
        >
          <TargetBars rows={data.domain_targets} />
        </ExhibitCard>
      )}
    </div>
  );
}
