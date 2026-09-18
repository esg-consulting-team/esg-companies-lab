import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { EvidenceBadge, ProvisionalBadge, UrgencyTag } from "../components/Badges";
import { useCompany } from "../state/CompanyContext";

const DOMAIN_KEYS = ["disclosure", "environment", "governance", "sector"];

export default function L3ItemDetail() {
  const { company } = useCompany();
  const [searchParams, setSearchParams] = useSearchParams();
  const itemCode = searchParams.get("item");

  const [sidebarItems, setSidebarItems] = useState([]);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company) return;
    Promise.all(DOMAIN_KEYS.map((k) => api.domainItems(company, k).catch(() => null)))
      .then((results) => {
        const merged = results
          .filter(Boolean)
          .flatMap((r) => r.items)
          .sort((a, b) => a.item_code.localeCompare(b.item_code));
        setSidebarItems(merged);
        if (!itemCode && merged.length > 0) {
          setSearchParams({ item: merged[0].item_code });
        }
      })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [company]);

  useEffect(() => {
    if (!company || !itemCode) return;
    setDetail(null);
    setError(null);
    api.itemDetail(company, itemCode).then(setDetail).catch((err) => setError(err.message));
  }, [company, itemCode]);

  return (
    <div className="l3-layout">
      <div className="item-list">
        {sidebarItems.map((item) => (
          <div
            key={item.item_code}
            className={`item-list-row${item.item_code === itemCode ? " active" : ""}`}
            onClick={() => setSearchParams({ item: item.item_code })}
          >
            <span className="code">{item.item_code}</span>
            <span className="num mono">{item.score.toFixed(0)}/100</span>
          </div>
        ))}
      </div>

      <div>
        {error && <div className="empty-state">불러오기 실패: {error}</div>}
        {!detail && !error && <div className="loading">불러오는 중…</div>}

        {detail && (
          <>
            <div className="item-header">
              <div className="item-header-top">
                <span className="item-header-code mono">{detail.item_code}</span>
                <span className="serif" style={{ fontSize: "var(--fs-headline1)", fontWeight: 600 }}>
                  {detail.item_name}
                </span>
                <UrgencyTag urgency={detail.urgency} />
                <span className="upper-label">{detail.scoring_type}</span>
              </div>
              <div className="item-header-score-row">
                <div>
                  <span className="kpi-label">현재 점수</span>
                  <span className="value num" style={{ color: detail.score === 0 ? "var(--crit)" : "var(--ink)" }}>
                    {detail.score.toFixed(0)} / {detail.max_score.toFixed(0)}
                    <ProvisionalBadge />
                  </span>
                </div>
                <div>
                  <span className="kpi-label">근거충분성</span>
                  <span className="value">
                    <EvidenceBadge level={detail.evidence_sufficiency} />
                  </span>
                </div>
                <div>
                  <span className="kpi-label">개선 시</span>
                  <span className="value num" style={{ color: "var(--good)" }}>
                    +{(detail.max_score - detail.score).toFixed(0)}
                  </span>
                </div>
              </div>
            </div>

            {detail.criteria_detail && (
              <div className="field-block">
                <div className="field-label">점검기준 (K-ESG 원문)</div>
                <div className="quote-block">{detail.criteria_detail}</div>
              </div>
            )}

            {detail.guideline_background && (
              <div className="field-block">
                <div className="field-label">판단 배경 (가이드라인 설명)</div>
                <div className="field-body">{truncate(detail.guideline_background, 500)}</div>
              </div>
            )}

            {detail.narrative ? (
              <div className="field-block">
                <div className="field-label">진단 결과 서술</div>
                {detail.narrative.fulfilled_level_text && (
                  <div className="narrative-fulfilled">{detail.narrative.fulfilled_level_text}</div>
                )}
                <div className="narrative-grid">
                  <div>
                    <div className="narrative-card-label">현황</div>
                    <div className="field-body" style={{ fontSize: 12.5 }}>
                      {detail.narrative.status || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="narrative-card-label">개선방향</div>
                    <div className="field-body" style={{ fontSize: 12.5 }}>
                      {detail.narrative.improvement || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="narrative-card-label">후속액션</div>
                    <div className="field-body" style={{ fontSize: 12.5 }}>
                      {detail.narrative.followup || "—"}
                    </div>
                  </div>
                </div>
                {detail.narrative.benchmark_case && (
                  <details style={{ marginTop: 14 }}>
                    <summary style={{ cursor: "pointer", fontSize: 12.5, color: "var(--navy)" }}>
                      벤치마킹 사례 비교 보기
                    </summary>
                    <div className="field-body" style={{ fontSize: 12.5, marginTop: 8 }}>
                      {detail.narrative.benchmark_case}
                    </div>
                  </details>
                )}
              </div>
            ) : (
              <>
                <div className="field-block">
                  <div className="field-label">확인근거</div>
                  <div className="field-body">
                    {detail.evidence.confirmed_basis || "확인된 근거 텍스트가 없습니다."}
                  </div>
                  {detail.evidence.reference_pages && (
                    <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 6 }}>
                      근거페이지: {detail.evidence.reference_pages}
                    </div>
                  )}
                </div>

                {detail.evidence.deduction_note && (
                  <div className="field-block">
                    <div className="field-label">감점사유 / 검수 메모</div>
                    <div className="field-body">{detail.evidence.deduction_note}</div>
                  </div>
                )}

                <div className="field-block">
                  <div className="field-label">해결방안</div>
                  <div className="solution-grid">
                    <div>
                      <div className="solution-col-label">현재 문제점</div>
                      <div className="field-body" style={{ fontSize: 12.5 }}>
                        {detail.solution.current_problem || "—"}
                      </div>
                    </div>
                    <div>
                      <div className="solution-col-label">개선방향</div>
                      <div className="field-body" style={{ fontSize: 12.5 }}>
                        {detail.solution.direction || "—"}
                      </div>
                    </div>
                    <div>
                      <div className="solution-col-label">필요 근거</div>
                      <div className="field-body" style={{ fontSize: 12.5 }}>
                        {detail.solution.required_evidence || "—"}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {detail.audit_question && (
              <div className="field-block">
                <div className="field-label">실사 진단 질문</div>
                <div className="field-body" style={{ fontSize: 12.5, color: "var(--ink-2)" }}>
                  {detail.audit_question} <span className="upper-label">{detail.answer_format}</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function truncate(text, max) {
  if (!text || text.length <= max) return text;
  return text.slice(0, max) + "…";
}
