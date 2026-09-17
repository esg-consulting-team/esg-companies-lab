import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { EvidenceBadge } from "../components/Badges";
import { useCompany } from "../state/CompanyContext";

const PARSE_COLOR = { 완료: "var(--good)", "색인 중": "var(--warn)", 미제출: "var(--ink-3)" };

export default function L6EvidenceDataRoom() {
  const { company } = useCompany();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!company) return;
    setData(null);
    setError(null);
    api.documents(company).then(setData).catch((err) => setError(err.message));
  }, [company]);

  if (error) return <div className="empty-state">불러오기 실패: {error}</div>;
  if (!data) return <div className="loading">불러오는 중…</div>;

  return (
    <div>
      <ExhibitCard
        number={14}
        title={data.documents.length > 0 ? "적재 문서 현황" : "적재 문서 없음"}
        subtitle="파싱 완료 문서만 챗봇 검색 대상에 포함됩니다."
        source="증빙 데이터룸 등록 현황 · 등록된 회사만 표시"
      >
        {data.documents.length === 0 ? (
          <div className="empty-note">이 회사에 대해 등록된 문서가 없습니다.</div>
        ) : (
          <table className="plain">
            <thead>
              <tr>
                <th>문서</th>
                <th>유형</th>
                <th className="num">연도</th>
                <th className="num">분량</th>
                <th>파싱</th>
                <th className="num">연결 항목</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((d) => (
                <tr key={d.name}>
                  <td>{d.name}</td>
                  <td>{d.doc_type || "—"}</td>
                  <td className="num mono">{d.year ?? "—"}</td>
                  <td className="num mono">{d.size_label ?? "—"}</td>
                  <td style={{ color: PARSE_COLOR[d.parse_status] || "var(--ink-2)" }}>{d.parse_status}</td>
                  <td className="num mono">{d.linked_items}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ExhibitCard>

      <ExhibitCard
        number={15}
        title="데이터 갭 리스트"
        subtitle="근거가 불충분·부분적인 항목의 필요 증빙을 항목별로 역집계했습니다."
        source="2026년 채점 결과의 해결방안 필드에서 자동 추출"
      >
        {data.data_gaps.length === 0 ? (
          <div className="empty-note">모든 항목의 근거가 충분합니다.</div>
        ) : (
          <table className="plain">
            <thead>
              <tr>
                <th>항목</th>
                <th>근거충분성</th>
                <th>필요 증빙</th>
              </tr>
            </thead>
            <tbody>
              {data.data_gaps.map((g) => (
                <tr key={g.item_code} onClick={() => navigate(`/l3?item=${g.item_code}`)}>
                  <td>
                    <span className="mono">{g.item_code}</span> {g.item_name}
                  </td>
                  <td>
                    <EvidenceBadge level={g.evidence_sufficiency} />
                  </td>
                  <td style={{ fontSize: 12 }}>{g.required_evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ExhibitCard>

      <div className="exhibit">
        <div className="exhibit-title serif">증빙 업로드</div>
        <div className="exhibit-subtitle">
          업로드 → 파싱 → 인덱싱 → 컨설턴트 검수 (F6-03, 확장 단계 — 현재는 UI만 제공)
        </div>
        <hr className="exhibit-rule" />
        <div className="dropzone">PDF · XLSX · 이미지 파일을 여기로 끌어다 놓으세요 (최대 400MB)</div>
      </div>
    </div>
  );
}
