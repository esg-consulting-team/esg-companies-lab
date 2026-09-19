import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { EvidenceBadge, ExhibitCard, StateMessage, formatNum, formatPct } from "../components/common";

const FOOTNOTE =
  "문서명은 채점 근거 텍스트에서 키워드로 추출한 근사치이며, 자유서술 특성상 일부 항목은 인식되지 않아 '미분류'로 표시될 수 있습니다. 실제 원문 확인은 L3 항목 상세의 확인근거 텍스트를 참고하세요.";

export function L6EvidenceDataRoom() {
  const { company = "" } = useParams();
  const navigate = useNavigate();
  const coverage = useFetch(() => api.getEvidenceDocuments(company), [company]);
  const gaps = useFetch(() => api.getEvidenceGaps(company), [company]);

  const goItem = (code: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(code)}`);

  if (coverage.loading || gaps.loading) return <StateMessage>불러오는 중…</StateMessage>;
  if (coverage.error || !coverage.data) return <StateMessage error>{coverage.error ?? "데이터를 불러오지 못했습니다."}</StateMessage>;
  if (gaps.error || !gaps.data) return <StateMessage error>{gaps.error ?? "데이터를 불러오지 못했습니다."}</StateMessage>;

  const { documentCounts, totalItems, unclassifiedCount, unclassifiedRate } = coverage.data;
  const maxCount = Math.max(1, ...documentCounts.map((d) => d.count));

  return (
    <div className="main__grid">
      <ExhibitCard
        number={1}
        eyebrow="참고자료 현황"
        title="참고자료 유형별 연결 항목 수"
        subtitle="텍스트 마이닝 기반 근사치 — 한 항목이 여러 문서를 동시에 언급하면 각 문서에 중복 집계됩니다."
        source="2026년 손채점·AI보조채점 메모 키워드 매칭"
      >
        {documentCounts.map((d) => (
          <div className={`hbar-row ${d.label === "미분류" ? "hbar-row--muted" : ""}`} key={d.label}>
            <span className="hbar-row__label">{d.label}</span>
            <div className="hbar-row__track">
              <div className="hbar-row__fill" style={{ width: `${(d.count / maxCount) * 100}%` }} />
            </div>
            <span className="hbar-row__meta">{formatNum(d.count)}건</span>
          </div>
        ))}
        <p className="evidence-doc-summary">
          미분류 {formatNum(unclassifiedCount)}건 / 전체 {formatNum(totalItems)}건 · {formatPct(unclassifiedRate)}
        </p>
        <p className="exhibit__source" style={{ marginTop: 4 }}>
          {FOOTNOTE}
        </p>
      </ExhibitCard>

      <ExhibitCard
        number={2}
        eyebrow="데이터 갭 리스트"
        title={gaps.data.length ? "근거충분성이 불충분·부분인 항목" : "근거충분성 갭 항목 없음"}
        source="2026년 손채점 메모 기준 근거충분성 판정"
      >
        {gaps.data.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>항목코드</th>
                  <th>항목명</th>
                  <th>근거충분성</th>
                  <th style={{ textAlign: "right" }}>손실점수</th>
                </tr>
              </thead>
              <tbody>
                {gaps.data.map((g) => (
                  <tr key={g.code} className="clickable" onClick={() => goItem(g.code)}>
                    <td className="mono">{g.code}</td>
                    <td>{g.name}</td>
                    <td>
                      <EvidenceBadge level={g.evidence} />
                    </td>
                    <td className="num" style={{ color: "var(--crit)" }}>
                      {g.lostPoints !== null ? `−${formatNum(g.lostPoints)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <StateMessage>불충분·부분 항목이 없습니다.</StateMessage>
        )}
      </ExhibitCard>
    </div>
  );
}
