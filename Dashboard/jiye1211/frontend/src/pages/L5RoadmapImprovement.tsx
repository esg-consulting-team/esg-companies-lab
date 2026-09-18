import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { ExhibitCard, StateMessage, UrgencyDistribution } from "../components/common";
import type { RoadmapChip as RoadmapChipData } from "../types";

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
          <div className="roadmap-dday__note">출처: esg_disclosure_deadline · 컨설팅 보고서 §08 최종 로드맵</div>
        </section>
      )}

      <ExhibitCard
        number={1}
        eyebrow="4개년 실행 로드맵"
        title="연도별 단계 · 과제 · 관련 항목"
        source="esg_roadmap_stages/esg_roadmap_tasks · 컨설팅 보고서 §08 최종 로드맵"
      >
        <div className="roadmap-stages">
          {stages.map((stage) => (
            <div className="roadmap-stage-card" key={stage.stageNo}>
              <div className="roadmap-stage-card__head">
                <span className="roadmap-stage-card__year">{stage.year}</span>
                <span className="roadmap-stage-card__name">{stage.stageName}</span>
                {stage.urgencyLevel && <span className="roadmap-stage-card__caption">원문: {stage.urgencyLevel}</span>}
              </div>
              <UrgencyDistribution counts={stage.urgencyDistribution} />
              <ul className="roadmap-task-list">
                {stage.tasks.map((task) => (
                  <li className="roadmap-task" key={task.taskName}>
                    <div className="roadmap-task__name">{task.taskName}</div>
                    <div className="roadmap-task__chips">
                      {task.chips.map((chip, i) => (
                        <RoadmapChip key={i} chip={chip} onGoItem={goItem} onGoDomain={goDomain} />
                      ))}
                    </div>
                    {task.deliverables && <div className="roadmap-task__deliverables">산출물: {task.deliverables}</div>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </ExhibitCard>

      {urgencyCriteria.length > 0 && (
        <ExhibitCard
          number={2}
          eyebrow="시급성 판단 기준"
          title="즉시 · 중기 · 장기 분류 기준"
          source="esg_urgency_criteria · 컨설팅 보고서 §08 최종 로드맵"
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
