/** 점검기준(K-ESG 원문) 표시 — 원문 텍스트는 바꾸거나 요약하지 않고 줄바꿈·구조화만 한다. */

/** 원문 구조가 표준("레이블 | 설명 …")과 달라 파서를 타지 않고 최소 처리(줄바꿈)만 하는 항목 코드. */
export const EXCEPTION_ITEM_CODES = ["반도체-E-1", "반도체-E-3", "반도체-E-5", "E-10-5", "G-1-1", "G-3-3", "G-윤리경영-추가1"];

// 구간 시작 = 문자열 처음·줄바꿈·"|" 바로 뒤의 레이블 + ("|" 또는 ":"). 문장 중간의 일반 "|"는 레이블이 아니라서 분리되지 않는다.
const LABEL_RE = /(^|\n|\|)\s*((?:\d+단계|요건\d+|유형\s*\d+)(?:\s*\(-?\d+[^)]*\))?)\s{0,2}[|:]/g;
const NOTE_SPLIT_RE = /\s*\|\s*(?=[*※])/;

interface Section {
  label: string;
  text: string;
}
interface Parsed {
  preamble: string;
  sections: Section[];
  notes: string[];
}

export function parseCriteria(raw: string): Parsed | null {
  const matches = [...raw.matchAll(LABEL_RE)];
  if (matches.length === 0) return null;

  const sections: Section[] = matches.map((m, i) => {
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? (matches[i + 1].index ?? raw.length) : raw.length;
    return { label: m[2].trim(), text: raw.slice(start, end).trim() };
  });

  // 노트("*"·"※")는 항상 마지막 레이블 구간 뒤에만 온다.
  const last = sections[sections.length - 1];
  const parts = last.text.split(NOTE_SPLIT_RE);
  last.text = parts[0].trim();
  const notes = parts.slice(1).map((n) => n.trim().replace(/^[*※] ?/, "")).filter(Boolean);

  return { preamble: raw.slice(0, matches[0].index ?? 0).trim(), sections, notes };
}

/** 예외·파싱 실패 항목 공용 — "\n"만 문단으로 나눈다. */
function MinimalCriteria({ text }: { text: string }) {
  return (
    <div className="quote-block criteria-plain">
      {text.split("\n").map((line, i) => (
        <p key={i}>{line}</p>
      ))}
    </div>
  );
}

export function CriteriaDetail({ code, text }: { code: string; text: string }) {
  const isException = EXCEPTION_ITEM_CODES.includes(code);
  const parsed = isException ? null : parseCriteria(text);

  if (!parsed) {
    return (
      <>
        <p className="criteria-caption">이 항목은 원문 구조가 표준과 달라 레이블 강조 없이 최소 정리만 적용됨</p>
        <MinimalCriteria text={text} />
      </>
    );
  }

  return (
    <div className="criteria-parsed">
      {parsed.preamble && <p className="criteria-row__text">{parsed.preamble}</p>}
      {parsed.sections.map((s, i) => (
        <div className="criteria-row" key={i}>
          <span className="criteria-row__label">{s.label}</span>
          <span className="criteria-row__text">{s.text}</span>
        </div>
      ))}
      {parsed.notes.length > 0 && (
        <div className="criteria-notes">
          <span className="criteria-notes__title">참고</span>
          <ul>
            {parsed.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
