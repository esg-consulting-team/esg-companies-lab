import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { DonutGauge } from "../components/DonutGauge";
import {
  ExhibitCard,
  GradeChip,
  NoData,
  StateMessage,
  formatNum,
  formatPct,
  gradeStyle,
} from "../components/common";
import type { DomainBucketKey, DomainDetail } from "../types";

const DOMAIN_ORDER: { key: DomainBucketKey }[] = [
  { key: "disclosure" },
  { key: "environment" },
  { key: "governance" },
  { key: "sector" },
];

/** L6 Exhibit 1과 동일한 각주 — 텍스트 마이닝 근사치라는 점을 리포트에서도 그대로 밝힌다. */
const DOC_COVERAGE_FOOTNOTE =
  "문서명은 채점 근거 텍스트에서 키워드로 추출한 근사치이며, 자유서술 특성상 일부 항목은 인식되지 않아 '미분류'로 표시될 수 있습니다. 실제 원문 확인은 L3 항목 상세의 확인근거 텍스트를 참고하세요.";

/** CriteriaPanel.tsx의 사회(S) 제외 근거 — 원문 그대로 옮긴 것(요약·수정 없음). L1~L6은 건드리지
 * 않고 여기서 독립적으로 다시 렌더링한다(같은 값을 공유 컴포넌트로 빼면 CriteriaPanel.tsx를
 * 고쳐야 하므로 의도적으로 중복시켰다). */
const SOCIAL_EXCLUSION_REASONS = [
  { label: "정보 접근성 한계", text: "외부 공개자료로는 정성적 S지표 변별력 확보 어려움" },
  { label: "평가 효율화", text: "S의 법/규제 위반만 사업보고서 공시로 일원화, 나머지는 E·G에 집중" },
  {
    label: "EDA 근거",
    text: "자체 점수-KCGS 등급 순위 일치도(Spearman) 사회 0.649 · 지배구조 0.577 · 환경 0.480(유일하게 낮음), KCGS C·D 취약군은 사회 대비 환경·지배구조 점수가 현저히 낮은 공통 패턴 확인",
  },
];

function domainOfCode(code: string): string {
  if (code.startsWith("반도체-")) return "반도체특화";
  if (code.startsWith("P-")) return "정보공시";
  if (code.startsWith("E-")) return "환경";
  if (code.startsWith("G-")) return "지배구조";
  return "기타";
}

const SECTIONS = [
  { key: "cover", no: "①", label: "표지" },
  { key: "summary", no: "②", label: "종합진단 요약" },
  { key: "domains", no: "③", label: "영역별 진단" },
  { key: "benchmark", no: "④", label: "벤치마킹 비교" },
  { key: "roadmap", no: "⑤", label: "개선 로드맵" },
  { key: "methodology", no: "⑥", label: "평가방법론 및 한계" },
  { key: "appendix", no: "⑦", label: "부록" },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];

async function fetchReportData(company: string) {
  const [summary, domainDetails, benchmark, roadmap, docs, reportComparison, profileCard] = await Promise.all([
    api.getSummary(company),
    Promise.all(DOMAIN_ORDER.map((d) => api.getDomainDetail(company, d.key))),
    api.getDomainBenchmark(company),
    api.getRoadmap(company),
    api.getEvidenceDocuments(company),
    api.getReportComparison(company).catch(() => null),
    api.getProfileCard(company).catch(() => null),
  ]);
  return { summary, domainDetails, benchmark, roadmap, docs, reportComparison, profileCard };
}

export function L7Report() {
  const { company = "" } = useParams();
  const { data, loading, error } = useFetch(() => fetchReportData(company), [company]);
  const [enabled, setEnabled] = useState<Record<SectionKey, boolean>>(
    Object.fromEntries(SECTIONS.map((s) => [s.key, true])) as Record<SectionKey, boolean>
  );

  if (loading) return <StateMessage>불러오는 중…</StateMessage>;
  if (error || !data) return <StateMessage error>{error ?? "데이터를 불러오지 못했습니다."}</StateMessage>;

  const { summary, domainDetails, benchmark, roadmap, docs, reportComparison, profileCard } = data;
  const companyMeta = summary.company;

  const domainRows = domainDetails.map((d: DomainDetail) => ({
    label: d.label,
    applicableCount: d.items.filter((it) => it.applicable).length,
    evidenceCounts: d.evidenceCounts,
  }));
  const totalApplicable = domainRows.reduce((sum, d) => sum + d.applicableCount, 0);

  const zeroByDomain: Record<string, number> = {};
  if (reportComparison) {
    for (const code of reportComparison.structuralZeroItems_3yearConsecutive) {
      const d = domainOfCode(code);
      zeroByDomain[d] = (zeroByDomain[d] ?? 0) + 1;
    }
  }
  const domainAvgByLabel = new Map((reportComparison?.domainScores ?? []).map((d) => [d.domain, d]));

  const maxDocCount = Math.max(1, ...docs.documentCounts.map((d) => d.count));

  return (
    <div className="main__grid">
      <section className="l7-toc no-print">
        <span className="l7-toc__title">목차</span>
        {SECTIONS.map((s) => (
          <label className="l7-toc__item" key={s.key}>
            <input
              type="checkbox"
              checked={enabled[s.key]}
              onChange={() => setEnabled((prev) => ({ ...prev, [s.key]: !prev[s.key] }))}
            />
            {s.no} {s.label}
          </label>
        ))}
      </section>

      <section className="l7-format-row no-print">
        <button className="l7-format-btn l7-format-btn--primary" onClick={() => window.print()}>
          PDF로 인쇄
        </button>
        <button className="l7-format-btn" disabled title="준비 중">
          XLSX (준비 중)
        </button>
        <button className="l7-format-btn" disabled title="준비 중">
          PPTX (준비 중)
        </button>
      </section>

      {enabled.cover && (
        <ExhibitCard number={1} eyebrow="표지" title={`${company} ESG 진단 리포트`} source="기업 개황 프로필">
          <div className="l7-cover">
            <div className="l7-cover__headline">
              {company} {companyMeta.sector && <span className="l7-cover__sector">· {companyMeta.sector}</span>}
            </div>
            {profileCard ? (
              <div className="field-block-grid">
                <div className="field-block">
                  <span className="field-block__label">종목코드</span>
                  <div className="field-block__value">{profileCard.stockCode ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">설립연도</span>
                  <div className="field-block__value">{profileCard.establishedYear ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">상장구분</span>
                  <div className="field-block__value">{profileCard.listingType ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">업종분류</span>
                  <div className="field-block__value">{profileCard.industryClassification ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">연결자산총액</span>
                  <div className="field-block__value">{profileCard.consolidatedAssets ?? <NoData />}</div>
                </div>
                <div className="field-block">
                  <span className="field-block__label">종업원수</span>
                  <div className="field-block__value">{profileCard.employeeCount ?? <NoData />}</div>
                </div>
                <div className="field-block" style={{ gridColumn: "1 / -1" }}>
                  <span className="field-block__label">주요사업</span>
                  <div className="field-block__value">{profileCard.mainBusiness ?? <NoData />}</div>
                </div>
              </div>
            ) : (
              <StateMessage>프로필 데이터가 없습니다.</StateMessage>
            )}
          </div>
        </ExhibitCard>
      )}

      {enabled.summary && (
        <ExhibitCard
          number={2}
          eyebrow="종합진단 요약"
          title="가채점 총점 · KCGS 등급 · 영역별 달성률"
          source="K-ESG v2.0 가이드라인 · 2026년 손채점 결과 · KCGS 공식등급"
        >
          <div className="kpi-row">
            <div className="kpi-cell">
              <span className="kpi-cell__label" style={{ fontSize: 9 }}>
                가채점 총점
              </span>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <DonutGauge
                  rate={summary.assessment.rate}
                  size={140}
                  r={54}
                  strokeWidth={12}
                  centerContent={{ label: "달성률", value: formatPct(summary.assessment.rate) }}
                />
              </div>
              <span className="tabular-nums" style={{ fontSize: 11, color: "var(--ink-3)", textAlign: "center" }}>
                {formatNum(summary.assessment.totalScore)} / {formatNum(summary.assessment.maxScore)}점 · 항목당 100점
                정규화 기준
              </span>
            </div>
            <div className="kpi-cell">
              <span className="kpi-cell__label">KCGS 공식등급</span>
              <div className="kpi-cell__value-row">
                <GradeChip grade={summary.officialGrade?.overall} />
                <span className="kpi-cell__sub">{summary.officialGrade ? `${summary.officialGrade.year}년` : "확인 필요"}</span>
              </div>
            </div>
            <div className="kpi-cell">
              <span className="kpi-cell__label">근거 불충분 항목</span>
              <span className="kpi-cell__value tabular-nums">
                {summary.evidenceCounts.불충분} / {summary.assessment.totalItems}
              </span>
            </div>
            <div className="kpi-cell">
              <span className="kpi-cell__label">개선 과제</span>
              <span className="kpi-cell__value tabular-nums">
                {summary.urgencyCounts.즉시 + summary.urgencyCounts.중기 + summary.urgencyCounts.장기} 건
              </span>
              <span className="kpi-cell__sub">
                즉시 {summary.urgencyCounts.즉시} · 중기 {summary.urgencyCounts.중기} · 장기 {summary.urgencyCounts.장기}
              </span>
            </div>
          </div>

          <div className="upper-label" style={{ margin: "16px 0 8px" }}>
            영역별 달성률
          </div>
          {summary.domains.map((d) => (
            <div key={d.key} className={`hbar-row ${d.rate === null ? "hbar-row--disabled" : ""}`}>
              <span className="hbar-row__label">{d.label}</span>
              <div className="hbar-row__track">
                <div className="hbar-row__fill" style={{ width: `${(d.rate ?? 0) * 100}%` }} />
              </div>
              <span className="hbar-row__meta">{d.rate === null ? "해당 없음" : formatPct(d.rate)}</span>
            </div>
          ))}

          <div className="upper-label" style={{ margin: "16px 0 8px" }}>
            3개년 KCGS 등급 추이
          </div>
          {summary.gradeHistory.length ? (
            <div className="grade-segments">
              {summary.gradeHistory.map((h) => {
                const style = gradeStyle(h.overall);
                return style ? (
                  <div key={h.year} className="grade-segment" style={{ background: style.bg, color: style.text }}>
                    {h.year} · {h.overall}
                  </div>
                ) : (
                  <div key={h.year} className="grade-segment grade-segment--empty">
                    {h.year} · 미평가
                  </div>
                );
              })}
            </div>
          ) : (
            <StateMessage>등급 추이 데이터가 없습니다.</StateMessage>
          )}
        </ExhibitCard>
      )}

      {enabled.domains && (
        <ExhibitCard
          number={3}
          eyebrow="영역별 진단"
          title="영역별 근거충분성 요약"
          subtitle="항목 전체 목록이 아닌 영역별 집계만 표시합니다 — 상세는 L2를 참고하세요."
          source="2026년 손채점 결과 · 해당 항목 기준 집계"
        >
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>영역</th>
                  <th className="num">해당 항목수</th>
                  <th className="num">충분</th>
                  <th className="num">부분</th>
                  <th className="num">불충분</th>
                </tr>
              </thead>
              <tbody>
                {domainRows.map((d) => (
                  <tr key={d.label}>
                    <td>{d.label}</td>
                    <td className="num">{d.applicableCount}</td>
                    <td className="num">{d.evidenceCounts.충분 ?? 0}</td>
                    <td className="num">{d.evidenceCounts.부분 ?? 0}</td>
                    <td className="num">{d.evidenceCounts.불충분 ?? 0}</td>
                  </tr>
                ))}
                <tr className="total-row">
                  <td>합계</td>
                  <td className="num">{totalApplicable}</td>
                  <td className="num" colSpan={3} />
                </tr>
              </tbody>
            </table>
          </div>
        </ExhibitCard>
      )}

      {enabled.benchmark && (
        <ExhibitCard
          number={4}
          eyebrow="벤치마킹 비교"
          title="자사 vs 벤치마킹군 도메인별 채점값"
          source="벤치마킹사 개별 채점값(팀 채점표 기준)"
        >
          {benchmark.self ? (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>회사</th>
                    <th className="num">종합</th>
                    <th className="num">정보공시</th>
                    <th className="num">환경</th>
                    <th className="num">지배구조</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <strong>{benchmark.self.company} (자사)</strong>
                    </td>
                    <td className="num">{benchmark.self.overall ?? <NoData />}</td>
                    <td className="num">{benchmark.self.disclosure ?? <NoData />}</td>
                    <td className="num">{benchmark.self.environment ?? <NoData />}</td>
                    <td className="num">{benchmark.self.governance ?? <NoData />}</td>
                  </tr>
                  {benchmark.peers.map((p) => (
                    <tr key={p.company}>
                      <td>{p.company}</td>
                      <td className="num">{p.overall ?? <NoData />}</td>
                      <td className="num">{p.disclosure ?? <NoData />}</td>
                      <td className="num">{p.environment ?? <NoData />}</td>
                      <td className="num">{p.governance ?? <NoData />}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <StateMessage>벤치마킹 비교 데이터가 없습니다.</StateMessage>
          )}
        </ExhibitCard>
      )}

      {enabled.roadmap && (
        <ExhibitCard
          number={5}
          eyebrow="개선 로드맵"
          title="4개년 실행 로드맵 요약"
          subtitle="과제 전체 목록이 아닌 단계별 요약만 표시합니다 — 상세는 L5를 참고하세요."
          source="컨설팅보고서 §08 최종 로드맵"
        >
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>연도</th>
                  <th>단계명</th>
                  <th className="num">과제 수</th>
                </tr>
              </thead>
              <tbody>
                {roadmap.stages.map((s) => (
                  <tr key={s.stageNo}>
                    <td className="mono">{s.year}</td>
                    <td>{s.stageName}</td>
                    <td className="num">{s.tasks.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {roadmap.yearMismatchNote && <p className="roadmap-dday__caveat">※ {roadmap.yearMismatchNote}</p>}
          {roadmap.disclosureDeadline && (
            <p className="exhibit__source" style={{ marginTop: 4 }}>
              실질 준비 기간 — {roadmap.disclosureDeadline["실질 준비 기간"]}
            </p>
          )}
        </ExhibitCard>
      )}

      {enabled.methodology && (
        <ExhibitCard
          number={6}
          eyebrow="평가방법론 및 한계"
          title="참고데이터 · 채점범위 · 사회(S) 제외 근거 · 진단의 한계"
          source="컨설팅보고서 3개년 분석"
        >
          {reportComparison ? (
            <>
              <div className="field-block">
                <span className="field-block__label">참고데이터</span>
                <div className="field-block__value">
                  벤치마킹 {reportComparison.benchmarkCompanyCount}개사 ({reportComparison.benchmarkAliases.join(", ")})
                </div>
              </div>
              <div className="field-block">
                <span className="field-block__label">평가원칙</span>
                <div className="field-block__value">{reportComparison.totalScore.scale}</div>
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
                    {Object.entries(reportComparison.itemBreakdown).map(([domain, count]) => {
                      const avg = domainAvgByLabel.get(domain);
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

              <div className="criteria-panel__social-exclusion" style={{ marginTop: 16 }}>
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
              </div>

              <div className="upper-label" style={{ margin: "16px 0 8px" }}>
                본 진단의 한계
              </div>
              <ul className="criteria-panel__reason-list">
                {reportComparison.generalLimitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </>
          ) : (
            <StateMessage>방법론 데이터가 없습니다.</StateMessage>
          )}
        </ExhibitCard>
      )}

      {enabled.appendix && (
        <ExhibitCard
          number={7}
          eyebrow="부록"
          title="참고자료 현황"
          source="2026년 손채점·AI보조채점 메모 키워드 매칭"
        >
          {docs.documentCounts.map((d) => (
            <div className={`hbar-row ${d.label === "미분류" ? "hbar-row--muted" : ""}`} key={d.label}>
              <span className="hbar-row__label">{d.label}</span>
              <div className="hbar-row__track">
                <div className="hbar-row__fill" style={{ width: `${(d.count / maxDocCount) * 100}%` }} />
              </div>
              <span className="hbar-row__meta">{formatNum(d.count)}건</span>
            </div>
          ))}
          <p className="evidence-doc-summary">
            미분류 {formatNum(docs.unclassifiedCount)}건 / 전체 {formatNum(docs.totalItems)}건 ·{" "}
            {formatPct(docs.unclassifiedRate)}
          </p>
          <p className="exhibit__source" style={{ marginTop: 4 }}>
            {DOC_COVERAGE_FOOTNOTE}
          </p>
        </ExhibitCard>
      )}

      <ExhibitCard number={8} eyebrow="생성 이력" title="리포트 생성 이력" source="이번 스코프에서는 저장 기능이 없습니다">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>파일명</th>
                <th>형식</th>
                <th>생성일시</th>
                <th>생성자</th>
              </tr>
            </thead>
            <tbody />
          </table>
        </div>
        <StateMessage>아직 생성된 리포트가 없습니다.</StateMessage>
      </ExhibitCard>
    </div>
  );
}
