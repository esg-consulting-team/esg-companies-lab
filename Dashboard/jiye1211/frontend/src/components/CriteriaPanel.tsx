import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { NoData, StateMessage, formatNum } from "./common";

/** 항목코드 접두어로 도메인을 구분한다 — report_extracted_data.json의
 * structuralZeroItems_3yearConsecutive 배열(도메인 라벨 없이 코드만 있음)을
 * itemBreakdown의 영역별 집계와 맞춰 보여주기 위한 용도. */
function domainOfCode(code: string): string {
  if (code.startsWith("반도체-")) return "반도체특화";
  if (code.startsWith("P-")) return "정보공시";
  if (code.startsWith("E-")) return "환경";
  if (code.startsWith("G-")) return "지배구조";
  return "기타";
}

/** "사회(S) 영역 제외 근거" — 회사와 무관한 고정 설명. 문구·숫자를 요약·수정하지 않고 그대로 쓴다. */
const SOCIAL_EXCLUSION_REASONS = [
  {
    label: "정보 접근성 한계",
    text: "외부 공개자료로는 정성적 S지표 변별력 확보 어려움",
  },
  {
    label: "평가 효율화",
    text: "S의 법/규제 위반만 사업보고서 공시로 일원화, 나머지는 E·G에 집중",
  },
  {
    label: "EDA 근거",
    text: "자체 점수-KCGS 등급 순위 일치도(Spearman) 사회 0.649 · 지배구조 0.577 · 환경 0.480(유일하게 낮음), KCGS C·D 취약군은 사회 대비 환경·지배구조 점수가 현저히 낮은 공통 패턴 확인",
  },
];

export function CriteriaPanel({
  open,
  onClose,
  company,
}: {
  open: boolean;
  onClose: () => void;
  company: string;
}) {
  const { data, loading, error } = useFetch(() => api.getReportComparison(company), [company]);

  const zeroByDomain: Record<string, number> = {};
  if (data) {
    for (const code of data.structuralZeroItems_3yearConsecutive) {
      const d = domainOfCode(code);
      zeroByDomain[d] = (zeroByDomain[d] ?? 0) + 1;
    }
  }
  const domainAvg = new Map((data?.domainScores ?? []).map((d) => [d.domain, d]));
  const periodNote = data?.generalLimitations.find((l) => l.includes("평가년도") || l.includes("기준일"));

  return (
    <>
      <div className={`criteria-backdrop ${open ? "criteria-backdrop--open" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`criteria-panel ${open ? "criteria-panel--open" : ""}`} aria-hidden={!open}>
        <header className="criteria-panel__header">
          <span className="criteria-panel__title">평가 기준</span>
          <button className="criteria-panel__close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>
        <div className="criteria-panel__body">
          {loading && <StateMessage>불러오는 중…</StateMessage>}
          {error && <StateMessage error>{error}</StateMessage>}
          {data && (
            <>
              <section>
                <div className="upper-label" style={{ marginBottom: 10 }}>
                  참고데이터 · 분석기간 · 평가원칙
                </div>
                <div className="field-block">
                  <span className="field-block__label">참고데이터</span>
                  <div className="field-block__value">
                    벤치마킹 {data.benchmarkCompanyCount}개사 ({data.benchmarkAliases.join(", ")})
                  </div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">분석기간</span>
                  <div className="field-block__value">{periodNote ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">평가원칙</span>
                  <div className="field-block__value">{data.totalScore.scale}</div>
                </div>

                <div className="upper-label" style={{ margin: "16px 0 8px" }}>
                  채점범위
                </div>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>영역</th>
                        <th className="num">항목수</th>
                        <th className="num">평균</th>
                        <th className="num">3년 연속 미충족</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.itemBreakdown).map(([domain, count]) => {
                        const avg = domainAvg.get(domain);
                        return (
                          <tr key={domain}>
                            <td>{domain}</td>
                            <td className="num">{count}</td>
                            <td className="num">{avg ? `${formatNum(avg.self, 1)}%` : <NoData />}</td>
                            <td className="num">{zeroByDomain[domain] ?? 0}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="criteria-panel__social-exclusion">
                <div className="upper-label" style={{ marginBottom: 10 }}>
                  사회(S) 영역 제외 근거
                </div>
                <ul className="criteria-panel__reason-list">
                  {SOCIAL_EXCLUSION_REASONS.map((r) => (
                    <li key={r.label}>
                      <strong>{r.label}</strong> — {r.text}
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <div className="upper-label" style={{ marginBottom: 10 }}>
                  본 진단의 한계
                </div>
                <ul className="criteria-panel__reason-list">
                  {data.generalLimitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
