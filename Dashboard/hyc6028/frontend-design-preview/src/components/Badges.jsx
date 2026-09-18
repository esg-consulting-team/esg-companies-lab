import UrgencyHelp from "./UrgencyHelp";

// 등급색 6단계 — EDAcolor.txt 정본 (DESIGN.md §3.2), A+~D 그대로 매핑
const GRADE_CLASS = {
  "A+": "grade-a-plus",
  A: "grade-a",
  "B+": "grade-b-plus",
  B: "grade-b",
  C: "grade-c",
  D: "grade-d",
};

export function GradeChip({ grade }) {
  if (!grade) return <span className="grade-chip grade-mid mono">미확인</span>;
  const cls = GRADE_CLASS[grade] || "grade-mid";
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
