import UrgencyHelp from "./UrgencyHelp";

export function GradeChip({ grade }) {
  if (!grade) return <span className="grade-chip grade-mid mono">미확인</span>;
  const cls = ["A", "A+"].includes(grade)
    ? "grade-good"
    : ["B", "B+"].includes(grade)
    ? "grade-mid"
    : "grade-bad";
  return <span className={`grade-chip ${cls} mono`}>{grade}</span>;
}

export function EvidenceBadge({ level }) {
  const safe = level || "미확인";
  return <span className={`evidence-badge ev-${safe}`}>{safe}</span>;
}

export function UrgencyTag({ urgency, withHelp = true }) {
  if (!urgency) return null;
  return (
    <span className="urgency-tag-wrap">
      <span className={`urgency-tag u-${urgency}`}>{urgency}</span>
      {withHelp && <UrgencyHelp level={urgency} />}
    </span>
  );
}

export function ProvisionalBadge() {
  return <span className="provisional-badge">가채점</span>;
}
