import type { CSSProperties, ReactNode } from "react";
import type { EvidenceLevel, Urgency } from "../types";

/** KCGS 공식 6단계 등급 칩 색 — §13.2.1 배지 텍스트 색상 규칙을 그대로 따른다. */
const GRADE_STYLES: Record<string, { bg: string; text: string }> = {
  "A+": { bg: "var(--grade-a-plus)", text: "var(--ink-on-dark)" },
  A: { bg: "var(--grade-a)", text: "var(--ink-on-dark)" },
  "B+": { bg: "var(--grade-b-plus)", text: "var(--ink-on-light)" },
  B: { bg: "var(--grade-b)", text: "var(--ink-on-light)" },
  C: { bg: "var(--grade-c)", text: "var(--ink-on-dark)" },
  D: { bg: "var(--grade-d)", text: "var(--ink-on-dark)" },
};

/** KCGS 6단계 등급의 상대적 순위(높을수록 우수) — 전년 대비 등락 비교 전용. */
export const GRADE_RANK: Record<string, number> = { "A+": 6, A: 5, "B+": 4, B: 3, C: 2, D: 1 };

export function gradeStyle(grade: string | null | undefined): { bg: string; text: string } | null {
  return grade ? GRADE_STYLES[grade] ?? null : null;
}

export function GradeChip({ grade }: { grade: string | null | undefined }) {
  const style = gradeStyle(grade);
  if (!style) return <span className="grade-chip grade-chip--none">—</span>;
  return (
    <span className="grade-chip" style={{ background: style.bg, borderColor: style.bg, color: style.text }}>
      {grade}
    </span>
  );
}

/** 전년 대비 KCGS 등급 등락 화살표. 둘 중 하나라도 없으면(비교 불가) 아무것도 표시하지 않는다. */
export function GradeChangeArrow({
  current,
  previous,
}: {
  current: string | null | undefined;
  previous: string | null | undefined;
}) {
  if (!current || !previous) return null;
  const curRank = GRADE_RANK[current];
  const prevRank = GRADE_RANK[previous];
  if (curRank === undefined || prevRank === undefined) return null;
  if (curRank > prevRank) {
    return (
      <span className="mono" style={{ color: "var(--change-up)", fontSize: 13 }} title={`전년 ${previous} → ${current}`}>
        ▲
      </span>
    );
  }
  if (curRank < prevRank) {
    return (
      <span className="mono" style={{ color: "var(--change-down)", fontSize: 13 }} title={`전년 ${previous} → ${current}`}>
        ▼
      </span>
    );
  }
  return (
    <span className="mono" style={{ color: "var(--change-flat)", fontSize: 13 }} title={`전년 동일: ${current}`}>
      —
    </span>
  );
}

export function EvidenceBadge({ level }: { level: EvidenceLevel }) {
  const label = level ?? "평가 예정";
  const cls = level ? `evidence-badge--${level}` : "evidence-badge--none";
  return <span className={`evidence-badge ${cls}`}>{label}</span>;
}

/** 점수 기준 근거충분성 — L2 히트맵/L3 항목 헤더 전용. 80점 이상 충분 · 40점 이상 부분 ·
 * 그 미만 불충분. (근거충분성 필터 칩·집계는 여전히 서버의 텍스트 파싱 기준을 그대로 쓴다 —
 * 이 함수는 두 화면의 배지 표시에만 쓰인다.) */
export function evidenceLevelFromScore(score: number | null): EvidenceLevel {
  if (score === null) return null;
  if (score >= 80) return "충분";
  if (score >= 40) return "부분";
  return "불충분";
}

export function UrgencyTag({ urgency }: { urgency: Urgency }) {
  if (!urgency) return null;
  return <span className={`urgency-tag urgency-tag--${urgency}`}>{urgency}</span>;
}

export function MockBadge({ children = "샘플 데이터" }: { children?: ReactNode }) {
  return <span className="mock-badge">{children}</span>;
}

/** "판정 확인 중" 항목 배지 — db/report_extracted_data.json의 pendingItems. */
export function PendingBadge() {
  return <span className="pending-badge">확인중</span>;
}

/** null 값 필드용 표준 표시 — 임의로 값을 채우지 않고 "해당 데이터 없음"으로만 표시한다. */
export function NoData({ children = "해당 데이터 없음" }: { children?: ReactNode }) {
  return <span style={{ color: "var(--ink-3)" }}>{children}</span>;
}

export function ExhibitCard({
  number,
  eyebrow,
  title,
  subtitle,
  source,
  eyebrowRight,
  children,
  style,
}: {
  number: number;
  eyebrow: string;
  title: string;
  subtitle?: string;
  source?: string;
  eyebrowRight?: ReactNode;
  children: ReactNode;
  /** 화면 전용 색 오버라이드 등에 쓰는 탈출구(예: L2 도메인 제목 색). 대부분은 생략한다. */
  style?: CSSProperties;
}) {
  return (
    <section className="exhibit" style={style}>
      <div className="exhibit__eyebrow">
        <span>
          <strong>EXHIBIT {number}</strong> · {eyebrow}
        </span>
        {eyebrowRight}
      </div>
      <h3 className="exhibit__title">{title}</h3>
      {subtitle && <p className="exhibit__subtitle">{subtitle}</p>}
      <hr className="exhibit__rule" />
      <div className="exhibit__body">{children}</div>
      <hr className="exhibit__rule" />
      {source && <p className="exhibit__source">출처: {source}</p>}
    </section>
  );
}

/** 즉시/중기/장기 분포 바 — L1 Exhibit 4의 urgency-lanes와 동일한 마크업·CSS 클래스를 쓴다(§L1 참고,
 * L1 자체는 건드리지 않고 여기서 새로 공용화했다). */
export function UrgencyDistribution({ counts }: { counts: { 즉시: number; 중기: number; 장기: number } }) {
  const total = counts.즉시 + counts.중기 + counts.장기;
  return (
    <div className="urgency-lanes">
      {(["즉시", "중기", "장기"] as const).map((u) => (
        <div className="urgency-lane" key={u}>
          <span className="kpi-cell__label">{u}</span>
          <span className="urgency-lane__count">{counts[u]}</span>
          <div className="urgency-lane__bar">
            <div
              className={`urgency-lane__bar-fill urgency-lane__bar-fill--${u}`}
              style={{ width: `${(counts[u] / Math.max(1, total)) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function StateMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <div className={`state-message ${error ? "state-message--error" : ""}`}>{children}</div>;
}

export function formatPct(rate: number | null | undefined, digits = 1) {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(digits)}%`;
}

export function formatNum(n: number | null | undefined, digits = 0) {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/** 0~100 득점률(또는 진척률)을 6단계(0~5) 중 하나로 나눈다 — 실제 색 계산은 CSS
 * color-mix()가 담당하고(.domain-tier-0~5), 여기서는 어느 단계인지만 고른다. */
export function scoreTier(rate0to100: number): number {
  return Math.min(5, Math.max(0, Math.floor(rate0to100 / (100 / 6))));
}
