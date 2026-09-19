import { useState } from "react";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { ExhibitCard, NoData, formatNum } from "./common";

/** 환경 원단위 3개년 추이 — 하나마이크론 전용. 값은 esg_diagnosis.note_scoring_model_25에서 확인된
 * 원문 수치 그대로이며, 다른 항목·다른 회사의 값은 채우지 않는다. */
const TREND_COMPANY = "하나마이크론";

const VERIFIED_TRENDS: { code: string; label: string; unit: string; years: number[]; values: number[] }[] = [
  { code: "E-5-1", label: "취수량 원단위", unit: "m³/억원", years: [2022, 2023, 2024], values: [85.5, 84.3, 59.33] },
  { code: "E-4-1", label: "에너지 원단위", unit: "TJ/억원", years: [2022, 2023, 2024], values: [0.136, 0.137, 0.095] },
];

/** 두 노트(자동채점·수기 검토)의 결론이 갈려 수치를 싣지 않는 항목. */
const UNVERIFIED_CODES = ["E-3-1", "E-6-1", "E-7-1", "반도체-E-2", "반도체-E-3", "반도체-E-5"];

const FOOTNOTE = "일부 항목은 채점 근거 간 결론이 달라 검증 후 반영 예정 — 담당 컨설턴트 확인 필요";
const UNVERIFIED_EXPLANATION = "자동채점 근거와 수기 검토 근거가 서로 다른 결론을 제시해 확인이 필요합니다";

const W = 300;
const H = 70;
const PAD_Y = 10;

/** 점 x좌표를 아래 표의 3열 중앙(1/6·3/6·5/6)에 맞춘다. */
function TrendLine({ values, color }: { values: number[]; color: string }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (W / values.length) * (i + 0.5);
    const y = PAD_Y + (1 - (v - min) / span) * (H - PAD_Y * 2);
    return [x, y] as const;
  });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="3개년 원단위 추이">
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={color} strokeWidth={2} />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={3.5} fill={color} />
      ))}
    </svg>
  );
}

export function EnvIntensityTrend({ company }: { company: string }) {
  const { data: items } = useFetch(() => api.listItems(company), [company]);
  const [openCode, setOpenCode] = useState<string | null>(null);

  if (company !== TREND_COMPANY) {
    return (
      <ExhibitCard number={13} eyebrow="환경 원단위 3개년 추이" title="환경 원단위 추이">
        <NoData>환경 원단위 3개년 데이터 미확보</NoData>
      </ExhibitCard>
    );
  }

  const nameOf = (code: string) => items?.find((it) => it.code === code)?.name ?? "";

  return (
    <ExhibitCard number={13} eyebrow="환경 원단위 3개년 추이" title="환경 원단위 추이" subtitle={FOOTNOTE}>
      <div className="grid-2">
        {VERIFIED_TRENDS.map((t) => {
          const first = t.values[0];
          const last = t.values[t.values.length - 1];
          const improved = last < first; // 원단위는 낮을수록 개선
          const color = improved ? "var(--change-up)" : "var(--change-down)";
          const pct = ((last - first) / first) * 100;
          return (
            <div key={t.code} className="field-block" style={{ borderBottom: "none" }}>
              <span className="field-block__label" style={{ textTransform: "none", letterSpacing: 0 }}>
                {t.code} · {t.label} ({t.unit})
              </span>
              <span style={{ fontSize: 12, color: "var(--ink-3)" }}>{nameOf(t.code)}</span>
              <TrendLine values={t.values} color={color} />
              <table className="data-table" style={{ tableLayout: "fixed" }}>
                <thead>
                  <tr>
                    {t.years.map((y) => (
                      <th key={y} style={{ textAlign: "center" }}>
                        {y}년
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {t.values.map((v, i) => (
                      <td key={i} className="tabular-nums" style={{ textAlign: "center" }}>
                        {v}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
              <span style={{ color, fontWeight: 700, fontSize: 13 }}>
                {improved ? "개선" : "악화"} · {formatNum(pct, 1)}%
              </span>
            </div>
          );
        })}
      </div>

      <div className="upper-label" style={{ margin: "14px 0 6px" }}>
        데이터 검증 필요 항목
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {UNVERIFIED_CODES.map((code) => (
          <button
            key={code}
            className="pill"
            onClick={() => setOpenCode(openCode === code ? null : code)}
            aria-expanded={openCode === code}
            style={{ color: "var(--warn)", background: "var(--warn-bg)", borderColor: "var(--warn)", cursor: "pointer", fontWeight: 700 }}
          >
            {code} · 데이터 검증 필요
          </button>
        ))}
      </div>
      {openCode && (
        <p style={{ fontSize: 12.5, color: "var(--ink-2)", margin: "8px 0 0" }}>
          <strong style={{ color: "var(--warn)" }}>{openCode}</strong>
          {nameOf(openCode) ? ` (${nameOf(openCode)})` : ""} — {UNVERIFIED_EXPLANATION}
        </p>
      )}
    </ExhibitCard>
  );
}
