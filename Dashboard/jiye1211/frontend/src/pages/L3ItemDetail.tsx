import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { EvidenceBadge, PendingBadge, StateMessage, UrgencyTag, formatNum } from "../components/common";

export function L3ItemDetail() {
  const { company = "", code } = useParams();
  const navigate = useNavigate();

  const { data: items } = useFetch(() => api.listItems(company), [company]);

  // code가 없으면 첫 번째(또는 0점) 항목으로 리다이렉트
  useEffect(() => {
    if (!code && items && items.length > 0) {
      const firstZero = items.find((it) => it.applicable && it.score === 0);
      const target = firstZero ?? items[0];
      navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(target.code)}`, { replace: true });
    }
  }, [code, items, company, navigate]);

  const { data: detail, loading, error } = useFetch(
    () => (code ? api.getItemDetail(company, code) : Promise.reject(new Error("no code"))),
    [company, code]
  );

  const goItem = (c: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(c)}`);

  return (
    <div className="item-detail-layout">
      <aside className="item-list">
        {items?.map((it) => (
          <div
            key={it.code}
            className={`item-list__row ${it.code === code ? "item-list__row--active" : ""}`}
            onClick={() => goItem(it.code)}
          >
            <span className="item-list__code">{it.code}</span>
            <span>
              {it.applicable ? `${formatNum(it.score)}/100` : "N/A"}
              {it.applicable && it.score === 0 ? " ●" : ""}
            </span>
          </div>
        ))}
      </aside>

      <div className="main__grid">
        {loading && <StateMessage>불러오는 중…</StateMessage>}
        {error && <StateMessage error>{error}</StateMessage>}
        {detail && (
          <>
            <div className="exhibit">
              <div className="item-header">
                <span className="item-header__code mono">{detail.code}</span>
                <h2 className="item-header__title">{detail.name}</h2>
                <div className="item-header__tags">
                  <span className="pill">{detail.domainLabel}</span>
                  {detail.scoringType && <span className="pill">{detail.scoringType}</span>}
                  <UrgencyTag urgency={detail.urgency} />
                  {detail.pendingReview && <PendingBadge />}
                </div>
                <div className="item-header__scores">
                  <div className="item-header__score-cell">
                    <span className="label">현재 점수</span>
                    <span className={`value ${detail.applicable && detail.score === 0 ? "value--zero" : ""}`}>
                      {detail.applicable ? `${formatNum(detail.score)} / 100` : "해당 없음"}
                    </span>
                  </div>
                  <div className="item-header__score-cell">
                    <span className="label">근거충분성</span>
                    <span className="value">
                      <EvidenceBadge level={detail.evidence} />
                    </span>
                  </div>
                  {detail.applicable && detail.score !== null && detail.score < 100 && (
                    <div className="item-header__score-cell">
                      <span className="label">개선 시</span>
                      <span className="value value--gain">+{formatNum(100 - detail.score)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {detail.pendingReview && (
              <div className="warning-banner warning-banner--warn">
                <strong>판정 확인 중</strong> — 현재 {formatNum(detail.pendingReview.currentScore)}점.{" "}
                {detail.pendingReview.pendingReason}
              </div>
            )}

            {detail.criteriaDetail && (
              <div className="exhibit">
                <div className="field-block">
                  <span className="field-block__label">점검기준 (K-ESG 원문)</span>
                  <div className="quote-block">{detail.criteriaDetail}</div>
                </div>

                {detail.scoringNote.structured ? (
                  <>
                    {detail.scoringNote.judgmentBasis && (
                      <div className="field-block">
                        <span className="field-block__label">판단근거</span>
                        <div className="field-block__value">{detail.scoringNote.judgmentBasis}</div>
                      </div>
                    )}
                    {detail.scoringNote.confirmedBasis && (
                      <div className="field-block">
                        <span className="field-block__label">확인근거</span>
                        <div className="field-block__value">{detail.scoringNote.confirmedBasis}</div>
                      </div>
                    )}
                    {detail.scoringNote.deductionReason && (
                      <div className="field-block">
                        <span className="field-block__label">감점사유</span>
                        <div className="field-block__value">{detail.scoringNote.deductionReason}</div>
                      </div>
                    )}
                    {detail.scoringNote.requiredEvidenceNote && (
                      <div className="field-block">
                        <span className="field-block__label">보완필요증빙</span>
                        <div className="field-block__value">{detail.scoringNote.requiredEvidenceNote}</div>
                      </div>
                    )}
                  </>
                ) : detail.scoringNote.raw ? (
                  <div className="field-block">
                    <span className="field-block__label">채점 메모 (원문 · 미구조화)</span>
                    <div className="field-block__value">{detail.scoringNote.raw}</div>
                  </div>
                ) : null}

                {detail.dataSource && (
                  <div className="field-block">
                    <span className="field-block__label">참고 자료 출처</span>
                    <div className="field-block__value">{detail.dataSource}</div>
                  </div>
                )}

                {detail.evidenceSources.length > 0 && (
                  <p className="evidence-source-caption">출처: {detail.evidenceSources.join(" · ")}</p>
                )}
              </div>
            )}

            {detail.solutionSplit.raw && (
              <div className="exhibit">
                <div className="exhibit__eyebrow">
                  <span>해결방안</span>
                </div>
                {detail.solutionSplit.structured ? (
                  <div className="solution-grid">
                    <div className="solution-grid__col">
                      <span className="solution-grid__col-label">현재 문제점</span>
                      <div className="solution-grid__col-body">{detail.solutionSplit.problem ?? "—"}</div>
                    </div>
                    <div className="solution-grid__col">
                      <span className="solution-grid__col-label">개선방향</span>
                      <div className="solution-grid__col-body">{detail.solutionSplit.direction ?? "—"}</div>
                    </div>
                    <div className="solution-grid__col">
                      <span className="solution-grid__col-label">필요 근거</span>
                      <div className="solution-grid__col-body">{detail.solutionSplit.evidence ?? "—"}</div>
                    </div>
                  </div>
                ) : (
                  <div className="field-block__value">{detail.solutionSplit.raw}</div>
                )}
              </div>
            )}

            {detail.dueDiligenceQuestion && (
              <div className="exhibit">
                <div className="field-block">
                  <span className="field-block__label">실사 진단 질문</span>
                  <div className="field-block__value">
                    {detail.dueDiligenceQuestion}
                    {detail.answerFormat && (
                      <span style={{ color: "var(--ink-3)" }}> ({detail.answerFormat})</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
