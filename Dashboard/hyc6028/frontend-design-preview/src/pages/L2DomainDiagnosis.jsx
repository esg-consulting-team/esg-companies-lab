import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ExhibitCard from "../components/ExhibitCard";
import { EvidenceBadge, UrgencyTag } from "../components/Badges";
import { useCompany } from "../state/CompanyContext";

const DOMAIN_TABS = [
  { key: "disclosure", label: "정보공시" },
  { key: "environment", label: "환경 E" },
  { key: "governance", label: "지배구조 G" },
  { key: "sector", label: "업종특화" },
  { key: "social", label: "사회 S", disabled: true },
];

export default function L2DomainDiagnosis() {
  const { company } = useCompany();
  const [domainKey, setDomainKey] = useState("environment");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [evidenceFilter, setEvidenceFilter] = useState(null);
  const [urgencyFilter, setUrgencyFilter] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!company) return;
    setData(null);
    setError(null);
    api
      .domainItems(company, domainKey)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [company, domainKey]);

  const filteredItems = useMemo(() => {
    if (!data) return [];
    return data.items.filter((item) => {
      if (evidenceFilter && item.evidence_sufficiency !== evidenceFilter) return false;
      if (urgencyFilter && item.urgency !== urgencyFilter) return false;
      return true;
    });
  }, [data, evidenceFilter, urgencyFilter]);

  const evidenceCounts = useMemo(() => {
    const counts = { 충분: 0, 부분: 0, 부분적: 0, 불충분: 0, 미확인: 0 };
    (data?.items || []).forEach((i) => {
      counts[i.evidence_sufficiency] = (counts[i.evidence_sufficiency] || 0) + 1;
    });
    return counts;
  }, [data]);

  const urgencyCounts = useMemo(() => {
    const counts = { 즉시: 0, 중기: 0, 장기: 0 };
    (data?.items || []).forEach((i) => {
      if (i.urgency in counts) counts[i.urgency] += 1;
    });
    return counts;
  }, [data]);

  return (
    <div>
      <div className="chip-row">
        {DOMAIN_TABS.map((t) => (
          <button
            key={t.key}
            className={`chip${domainKey === t.key ? " active" : ""}`}
            disabled={t.disabled}
            style={t.disabled ? { opacity: 0.45 } : undefined}
            onClick={() => setDomainKey(t.key)}
          >
            {t.label}
            {t.disabled ? " · 예정" : ""}
          </button>
        ))}
      </div>

      <div className="chip-row">
        {["충분", "부분", "불충분"].map((lv) => (
          <button
            key={lv}
            className={`chip${evidenceFilter === lv ? " active" : ""}`}
            onClick={() => setEvidenceFilter(evidenceFilter === lv ? null : lv)}
          >
            근거 {lv} {evidenceCounts[lv] || 0}
          </button>
        ))}
        {["즉시", "중기", "장기"].map((u) => (
          <button
            key={u}
            className={`chip${urgencyFilter === u ? " active" : ""}`}
            onClick={() => setUrgencyFilter(urgencyFilter === u ? null : u)}
          >
            {u} {urgencyCounts[u] || 0}
          </button>
        ))}
      </div>

      {error && <div className="empty-state">불러오기 실패: {error}</div>}
      {!data && !error && <div className="loading">불러오는 중…</div>}

      {data && (
        <ExhibitCard
          number={6}
          title={`${data.label} 항목 히트맵`}
          subtitle={`${data.items.length}개 항목 · 득점 ${data.achieved.toFixed(0)} / ${data.max_possible.toFixed(0)}. 0점 항목은 배경을 강조 표시합니다.`}
          source="2026년 채점 결과 기준 · 셀 클릭 시 항목 상세로 이동"
        >
          {filteredItems.length === 0 ? (
            <div className="empty-state">조건에 맞는 항목이 없습니다.</div>
          ) : (
            <div className="heatmap-grid">
              {filteredItems.map((item) => (
                <div
                  key={item.item_code}
                  className={`heat-cell${item.score === 0 ? " zero" : ""}`}
                  onClick={() => navigate(`/l3?item=${item.item_code}`)}
                >
                  <div className="heat-cell-code">{item.item_code}</div>
                  <div className="heat-cell-name">{item.item_name}</div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span className="heat-cell-score">{item.score.toFixed(0)}/100</span>
                    <EvidenceBadge level={item.evidence_sufficiency} />
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <UrgencyTag urgency={item.urgency} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </ExhibitCard>
      )}
    </div>
  );
}
