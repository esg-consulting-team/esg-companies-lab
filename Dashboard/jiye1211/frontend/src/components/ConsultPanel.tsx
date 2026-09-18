import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { ChatResponse } from "../types";

interface ChatTurn {
  question: string;
  loading: boolean;
  response?: ChatResponse;
  error?: string;
}

/**
 * AI 상담 패널 (F5).
 *
 * db/chroma_db_migrated에서 되살린 회사별 사업/지배구조/지속가능경영보고서 청크를
 * Gemini 임베딩으로 재색인(backend/scripts/build_rag_index.py)해두고, 질문이 오면
 * 코사인 유사도로 상위 문서를 찾아 그 내용만 근거로 Gemini가 답하게 한다
 * (근거 밖 내용은 단정하지 말라고 시스템 프롬프트에 명시 — F5-03).
 */
export function ConsultPanel({
  open,
  onToggle,
  contextLabel,
  company,
  itemCode,
}: {
  open: boolean;
  onToggle: () => void;
  contextLabel: string;
  company: string;
  itemCode?: string;
}) {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  if (!open) {
    return (
      <button className="consult__strip" onClick={onToggle} aria-label="AI 상담 패널 펼치기">
        AI 상담
      </button>
    );
  }

  const ask = async (question: string) => {
    const history = turns
      .filter((t) => t.response)
      .slice(-3)
      .map((t) => ({ question: t.question, conclusion: t.response!.conclusion }));
    setTurns((prev) => [...prev, { question, loading: true }]);
    try {
      const response = await api.chat(company, question, itemCode, history);
      setTurns((prev) => prev.map((t) => (t.question === question && t.loading ? { ...t, loading: false, response } : t)));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "답변을 가져오지 못했습니다.";
      setTurns((prev) => prev.map((t) => (t.question === question && t.loading ? { ...t, loading: false, error: msg } : t)));
    }
  };

  return (
    <aside className="consult">
      <div className="consult__panel">
        <div className="consult__header">
          <span className="consult__title">AI 상담</span>
          <button className="consult__collapse" onClick={onToggle} aria-label="AI 상담 패널 접기">
            »
          </button>
        </div>
        <span className="consult__context-badge">{contextLabel}</span>

        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          {turns.length === 0 && (
            <p className="consult__conclusion" style={{ color: "var(--ink-3)" }}>
              이 화면·항목에 대해 궁금한 점을 물어보세요. 답변은 이 회사의 사업보고서·지배구조보고서·
              지속가능경영보고서에서 찾은 내용에만 근거합니다.
            </p>
          )}

          {turns.map((t, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>Q. {t.question}</div>

              {t.loading && (
                <p className="consult__conclusion" style={{ color: "var(--ink-3)" }}>
                  답변을 준비하는 중…
                </p>
              )}

              {t.error && (
                <p className="consult__conclusion" style={{ color: "var(--crit)" }}>
                  {t.error}
                </p>
              )}

              {t.response && (
                <>
                  <div>
                    <div className="consult__block-label">
                      결론
                      {t.response.viaWebSearch && (
                        <span className="pill" style={{ marginLeft: 6, color: "var(--warn)", borderColor: "var(--warn)" }}>
                          웹 검색 근거
                        </span>
                      )}
                    </div>
                    <p className="consult__conclusion">
                      {t.response.conclusion}
                      {t.response.insufficientEvidence && (
                        <span className="urgency-tag urgency-tag--중기" style={{ marginLeft: 6 }}>
                          근거 부족
                        </span>
                      )}
                    </p>
                  </div>

                  {t.response.citations.length > 0 && (
                    <div>
                      <div className="consult__block-label">근거{t.response.viaWebSearch ? " (웹)" : ""}</div>
                      {t.response.citations.map((c) => (
                        <div className="citation-card" key={c.n}>
                          <div className="citation-card__source">
                            [{c.n}]{" "}
                            {c.url ? (
                              <a href={c.url} target="_blank" rel="noopener noreferrer">
                                {c.doc}
                              </a>
                            ) : (
                              c.doc
                            )}
                            {c.page ? ` · p.${c.page}` : ""}
                          </div>
                          {c.tableHtml ? (
                            <div className="citation-table-scroll" dangerouslySetInnerHTML={{ __html: c.tableHtml }} />
                          ) : c.snippet ? (
                            <div>{c.snippet}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}

                  {t.response.nextAction && (
                    <div>
                      <div className="consult__block-label">다음 행동</div>
                      <p className="consult__conclusion">{t.response.nextAction}</p>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        <form
          style={{ display: "flex", gap: 6 }}
          onSubmit={(e) => {
            e.preventDefault();
            const q = draft.trim();
            if (!q) return;
            setDraft("");
            void ask(q);
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="질문을 입력하세요"
            style={{
              flex: 1,
              border: "1px solid var(--rule-mid)",
              padding: "6px 8px",
              fontSize: 12.5,
              background: "var(--paper)",
              color: "var(--ink)",
            }}
          />
          <button
            type="submit"
            style={{
              border: "1px solid var(--navy)",
              background: "var(--navy)",
              color: "var(--ink-on-dark)",
              padding: "6px 10px",
              fontSize: 12.5,
              cursor: "pointer",
            }}
          >
            전송
          </button>
        </form>

        <p className="consult__footer">
          답변은 적재된 자사 문서에서만 생성됩니다. 근거를 찾지 못하면 추정하지 않고 필요한 증빙을
          안내합니다.
        </p>
      </div>
    </aside>
  );
}
