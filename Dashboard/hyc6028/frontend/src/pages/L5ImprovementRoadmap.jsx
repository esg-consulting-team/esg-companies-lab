import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { useCompany } from "../state/CompanyContext";

const TIMELINE_START = new Date(2026, 0, 1);
const TIMELINE_MONTHS = 48; // 2026~2029, 4개년

function monthOffset(startMonth) {
  if (!startMonth) return null;
  const [y, m] = startMonth.split("-").map(Number);
  return (y - TIMELINE_START.getFullYear()) * 12 + (m - 1);
}

function Gantt({ tasks }) {
  const lanes = ["즉시", "중기", "장기"];
  const years = [2026, 2027, 2028, 2029];
  return (
    <div className="gantt">
      <div className="gantt-year-axis">
        <span />
        <div className="gantt-year-labels">
          {years.map((y) => (
            <span key={y}>{y}</span>
          ))}
        </div>
      </div>
      {lanes.map((lane) => {
        const laneTasks = tasks.filter((t) => t.lane === lane);
        if (laneTasks.length === 0) return null;
        return (
          <div key={lane}>
            <div className="gantt-lane-header">
              {lane} ({laneTasks.length}건)
            </div>
            {laneTasks.map((t) => {
              const offset = monthOffset(t.start_month);
              return (
                <div className="gantt-row" key={t.id}>
                  <div>
                    <div>{t.task}</div>
                    <div style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
                      {t.item_code || "공통"} {t.owner ? `· ${t.owner}` : ""}
                      {t.dependency ? ` · ${t.dependency}` : ""}
                    </div>
                  </div>
                  <div className="gantt-track">
                    {offset != null && t.months ? (
                      <div
                        className={`gantt-bar lane-${lane}`}
                        style={{
                          left: `${(offset / TIMELINE_MONTHS) * 100}%`,
                          width: `${(t.months / TIMELINE_MONTHS) * 100}%`,
                        }}
                      >
                        {t.months}개월
                      </div>
                    ) : (
                      <div style={{ fontSize: 10.5, color: "var(--ink-3)", paddingTop: 2 }}>
                        일정 미정 (+{t.gain.toFixed(0)}점)
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function RoiTable({ rows }) {
  if (rows.length === 0) {
    return <div className="empty-note">비용 정보가 등록된 과제가 없어 ROI를 계산할 수 없습니다.</div>;
  }
  return (
    <table className="plain">
      <thead>
        <tr>
          <th>과제</th>
          <th className="num">+점</th>
          <th className="num">비용(원)</th>
          <th className="num">점당 비용</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td>
              {r.item_code && <span className="mono">{r.item_code}</span>} {r.task}
            </td>
            <td className="num mono" style={{ color: "var(--good)" }}>
              +{r.gain.toFixed(0)}
            </td>
            <td className="num mono">{r.cost.toLocaleString()}</td>
            <td className="num mono">{r.cost_per_point.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Simulator({ company, tasks }) {
  const [selected, setSelected] = useState(() => new Set());
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    if (selected.size === 0) {
      setResult(null);
      return;
    }
    setBusy(true);
    setError(null);
    api
      .simulate(company, Array.from(selected))
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
  }, [selected, company]);

  return (
    <div className="exhibit">
      <div className="exhibit-title serif">점수 시뮬레이터</div>
      <div className="exhibit-subtitle">
        과제를 선택하면 서버에서 총점·달성률·예산·기간을 다시 계산합니다. (F4-04)
      </div>
      <hr className="exhibit-rule" />
      <div>
        {tasks.map((t) => (
          <div className="sim-task-row" key={t.id}>
            <label>
              <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggle(t.id)} />
              <span className="mono">{t.item_code || "공통"}</span>
              <span>{t.task}</span>
            </label>
            <span className="num mono" style={{ color: "var(--good)" }}>
              +{t.gain.toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {error && <div className="empty-note">계산 실패: {error}</div>}

      {result && (
        <div className="sim-result-box">
          <span className="sim-result-value num">
            {result.from_score.toFixed(0)} → {result.to_score.toFixed(0)} (+{result.gain.toFixed(0)})
          </span>
          <div style={{ fontSize: 12.5, color: "var(--ink-2)", marginTop: 6 }}>
            달성률 {(result.rate_from * 100).toFixed(1)}% → {(result.rate_to * 100).toFixed(1)}%
            {result.total_cost != null && ` · 예산 ${result.total_cost.toLocaleString()}원`}
            {result.max_months != null && ` · 최장 ${result.max_months}개월`}
            {result.cost_unknown_count > 0 && ` · 비용 미정 ${result.cost_unknown_count}건 제외`}
            {" · "}
            <span className="provisional-badge">예상치</span>
          </div>
          {busy && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>재계산 중…</div>}
        </div>
      )}
    </div>
  );
}

export default function L5ImprovementRoadmap() {
  const { company } = useCompany();
  const [roadmap, setRoadmap] = useState(null);
  const [roi, setRoi] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company) return;
    setRoadmap(null);
    setError(null);
    api.roadmap(company).then(setRoadmap).catch((err) => setError(err.message));
    api.roadmapRoi(company).then(setRoi).catch(() => setRoi([]));
  }, [company]);

  const gain = useMemo(() => (roadmap ? roadmap.tasks.reduce((s, t) => s + t.gain, 0) : 0), [roadmap]);

  if (error) return <div className="empty-state">불러오기 실패: {error}</div>;
  if (!roadmap) return <div className="loading">불러오는 중…</div>;

  return (
    <div>
      <ExhibitCard
        number={12}
        title="4개년 실행 로드맵"
        subtitle={
          roadmap.has_curated_data
            ? `즉시/중기/장기 과제 ${roadmap.tasks.length}건 · 합계 예상 +${gain.toFixed(0)}점`
            : `큐레이션된 일정·비용 데이터가 없어 실데이터(시급성·손실점수) 기준으로 자동 구성했습니다 · 합계 예상 +${gain.toFixed(0)}점`
        }
        source={roadmap.has_curated_data ? "roadmap_tasks (컨설턴트 큐레이션)" : "esg_diagnosis 자동 추출 · 예상치"}
      >
        <Gantt tasks={roadmap.tasks} />
      </ExhibitCard>

      <ExhibitCard
        number={13}
        title="ROI 우선순위"
        subtitle="점당 비용 = 예산 ÷ 예상 상승점. 낮을수록 효율이 높습니다."
        source="roadmap_tasks (비용 등록된 과제만)"
      >
        <RoiTable rows={roi} />
      </ExhibitCard>

      <Simulator company={company} tasks={roadmap.tasks} />
    </div>
  );
}
