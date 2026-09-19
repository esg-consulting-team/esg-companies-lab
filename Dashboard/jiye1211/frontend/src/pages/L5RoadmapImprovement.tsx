import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { ExhibitCard, StateMessage } from "../components/common";
import type { RoadmapChip as RoadmapChipData, RoadmapTask, UrgencyCounts } from "../types";

export const LEVELS = ["즉시", "중기", "장기"] as const;
type Level = (typeof LEVELS)[number];

/** 그 해 건수가 가장 많은 시급성(동률이면 즉시>중기>장기 순). 건수가 전부 0이면 null. */
function dominantLevel(counts: UrgencyCounts): Level | null {
  let best: Level | null = null;
  for (const level of LEVELS) {
    if (counts[level] > 0 && (best === null || counts[level] > counts[best])) best = level;
  }
  return best;
}

/** 과제의 시급성 = 과제에 딸린 항목코드 칩 중 가장 급한 시급성. 시급성이 있는 항목 칩이 없으면 null. */
export function taskLevel(task: RoadmapTask): Level | null {
  for (const level of LEVELS) {
    if (task.chips.some((c) => c.type === "item" && c.urgency === level)) return level;
  }
  return null;
}

function RoadmapChip({
  chip,
  onGoItem,
  onGoDomain,
}: {
  chip: RoadmapChipData;
  onGoItem: (code: string) => void;
  onGoDomain: (bucket: string) => void;
}) {
  if (chip.type === "non_scoring") {
    return <span className="roadmap-chip roadmap-chip--non_scoring">{chip.label}</span>;
  }
  if (chip.type === "domain") {
    return (
      <span
        className="roadmap-chip roadmap-chip--domain"
        onClick={() => chip.bucket && onGoDomain(chip.bucket)}
        title={chip.bucket ? "L2 해당 영역으로 이동" : undefined}
      >
        {chip.label}
      </span>
    );
  }
  return (
    <span className="roadmap-chip roadmap-chip--item mono" onClick={() => chip.code && onGoItem(chip.code)}>
      {chip.label}
    </span>
  );
}

export function L5RoadmapImprovement() {
  const { company = "" } = useParams();
  const navigate = useNavigate();
  const { data, loading, error } = useFetch(() => api.getRoadmap(company), [company]);

  const goItem = (code: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(code)}`);
  const goDomain = (bucket: string) => navigate(`/companies/${encodeURIComponent(company)}/l2/${encodeURIComponent(bucket)}`);

  if (loading) return <StateMessage>불러오는 중…</StateMessage>;
  if (error || !data) return <StateMessage error>{error ?? "데이터를 불러오지 못했습니다."}</StateMessage>;

  const { stages, urgencyCriteria, disclosureDeadline, yearMismatchNote } = data;

  return (
    <div className="main__grid">
      {disclosureDeadline && (
        <section className="roadmap-dday">
          <div>
            <strong>실질 준비 기간</strong> — {disclosureDeadline["실질 준비 기간"]}
          </div>
          {yearMismatchNote && <div className="roadmap-dday__caveat">※ {yearMismatchNote}</div>}
          {disclosureDeadline["공급망 요구"] && (
            <div className="roadmap-dday__note">공급망 요구 참고: {disclosureDeadline["공급망 요구"]}</div>
          )}
          <div className="roadmap-dday__note">출처: 컨설팅 보고서 §08 최종 로드맵</div>
        </section>
      )}

      <ExhibitCard
        number={1}
        eyebrow="4개년 실행 로드맵"
        title="연도별 단계 · 과제 · 관련 항목"
        source="컨설팅 보고서 §08 최종 로드맵"
      >
        <div className="roadmap-stages">
          {stages.map((stage) => (
            <div className="roadmap-stage-card" key={stage.stageNo}>
              <div className="roadmap-stage-card__head">
                <span className="roadmap-stage-card__year">{stage.year}</span>
                <span className="roadmap-stage-card__name">{stage.stageName}</span>
                {stage.urgencyLevel && <span className="roadmap-stage-card__caption">원문: {stage.urgencyLevel}</span>}
              </div>
              {dominantLevel(stage.urgencyDistribution) && (
                <div className="roadmap-stage-card__main">주요: {dominantLevel(stage.urgencyDistribution)}</div>
              )}
              {[...LEVELS, null].map((level) => {
                const tasks = stage.tasks.filter((t) => taskLevel(t) === level);
                if (level === null && tasks.length === 0) return null;
                const key = level ?? "none";
                return (
                  <section className={`roadmap-section roadmap-section--${key}`} key={key}>
                    <div className="roadmap-section__header">
                      <span className="roadmap-dot" aria-hidden="true" />
                      {level ?? "분류 없음"} ({tasks.length})
                    </div>
                    {tasks.length === 0 ? (
                      <p className="roadmap-section__empty">해당 연도에 {level} 과제가 없습니다</p>
                    ) : (
                      <ul className="roadmap-task-list">
                        {tasks.map((task) => (
                          <li className="roadmap-task" key={task.taskName}>
                            <div className="roadmap-task__name">
                              {level && <span className="roadmap-dot roadmap-dot--task" aria-hidden="true" />}
                              {task.taskName}
                            </div>
                            <div className="roadmap-task__chips">
                              {task.chips.map((chip, i) => (
                                <RoadmapChip key={i} chip={chip} onGoItem={goItem} onGoDomain={goDomain} />
                              ))}
                            </div>
                            {task.deliverables && (
                              <div className="roadmap-task__deliverables">산출물: {task.deliverables}</div>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                );
              })}
            </div>
          ))}
        </div>
      </ExhibitCard>

      {urgencyCriteria.length > 0 && (
        <ExhibitCard
          number={2}
          eyebrow="시급성 판단 기준"
          title="즉시 · 중기 · 장기 분류 기준"
          source="컨설팅 보고서 §08 최종 로드맵"
        >
          <div className="roadmap-criteria-grid">
            {urgencyCriteria.map((c) => (
              <div className="roadmap-criteria-card" key={c.level}>
                <span className="roadmap-criteria-card__level">{c.level}</span>
                {c.criteria}
              </div>
            ))}
          </div>
        </ExhibitCard>
      )}
    </div>
  );
}
