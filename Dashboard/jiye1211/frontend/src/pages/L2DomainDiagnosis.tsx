import { useMemo, useState, type CSSProperties } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { useCriteriaPanel } from "../context/CriteriaPanelContext";
import { ExhibitCard, EvidenceBadge, MockBadge, StateMessage, evidenceLevelFromScore, formatNum, scoreTier } from "../components/common";
import type { DomainBucketKey } from "../types";

const TABS: { key: DomainBucketKey; label: string }[] = [
  { key: "environment", label: "환경 E" },
  { key: "governance", label: "지배구조 G" },
  { key: "disclosure", label: "정보공시" },
  { key: "sector", label: "업종특화" },
];

/** L2 전용 도메인 아이덴티티 컬러 — 활성 탭 라벨·밑줄과 그 탭의 섹션 제목에만 쓴다.
 * Exhibit 배경·표 배경·칩 배경에는 절대 쓰지 않는다. §13.2의 --domain-* CSS 변수를 참조한다
 * (hex 직접 기입 금지) — 톤 재조정 시 tokens.css만 고치면 이 화면도 자동으로 같이 바뀐다. */
const DOMAIN_COLORS: Partial<Record<DomainBucketKey, string>> = {
  disclosure: "var(--domain-disclosure)",
  environment: "var(--domain-environment)",
  governance: "var(--domain-governance)",
  sector: "var(--domain-sector)",
};

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  next.has(value) ? next.delete(value) : next.add(value);
  return next;
}

export function L2DomainDiagnosis() {
  const { company = "", bucket = "environment" } = useParams();
  const navigate = useNavigate();
  const criteriaPanel = useCriteriaPanel();
  const activeBucket = (bucket as DomainBucketKey) ?? "environment";

  const { data, loading, error } = useFetch(
    () => api.getDomainDetail(company, activeBucket),
    [company, activeBucket]
  );

  const [evidenceFilter, setEvidenceFilter] = useState(new Set<string>());
  const [urgencyFilter, setUrgencyFilter] = useState(new Set<string>());
  const [scoringFilter, setScoringFilter] = useState(new Set<string>());

  const goItem = (code: string) => navigate(`/companies/${encodeURIComponent(company)}/l3/${encodeURIComponent(code)}`);

  const domainColor = DOMAIN_COLORS[activeBucket];

  const filteredItems = useMemo(() => {
    if (!data) return [];
    return data.items.filter((it) => {
      if (evidenceFilter.size && !(it.evidence && evidenceFilter.has(it.evidence))) return false;
      if (urgencyFilter.size && !(it.urgency && urgencyFilter.has(it.urgency))) return false;
      if (scoringFilter.size && !(it.scoringType && scoringFilter.has(it.scoringType))) return false;
      return true;
    });
  }, [data, evidenceFilter, urgencyFilter, scoringFilter]);

  const stageItems = useMemo(
    () =>
      (data?.items ?? []).filter(
        (it) => it.currentStage !== null && it.maxStageCount !== null && it.currentStage < (it.maxStageCount ?? 0)
      ),
    [data]
  );

  return (
    <div className="main__grid">
      <div className="tab-row">
        {TABS.map((t) => {
          const active = activeBucket === t.key;
          const tColor = active ? DOMAIN_COLORS[t.key] : undefined;
          return (
            <button
              key={t.key}
              className={`tab ${active ? "tab--active" : ""}`}
              style={tColor ? { color: tColor, borderBottomColor: tColor } : undefined}
              onClick={() => navigate(`/companies/${encodeURIComponent(company)}/l2/${t.key}`)}
            >
              {t.label} {data && t.key === activeBucket ? `(${data.summary.itemCount})` : ""}
            </button>
          );
        })}
        {/* 사회(S) — 진단 범위 밖이라 이동 가능한 탭이 아니다. hover/focus 시 제외 근거로
            이어지는 링크를 펼쳐 보여준다(평가 기준 패널은 기존 CriteriaPanel을 그대로 재사용). */}
        <div className="tab-social">
          <span className="tab tab-social__label">사회 S</span>
          <div className="tab-social__popover">
            <div className="tab-social__popover-title">사회(S) 진단범위 제외</div>
            <button className="criteria-banner" onClick={criteriaPanel.open}>
              제외 근거 보기
            </button>
          </div>
        </div>
      </div>

      {loading && <StateMessage>불러오는 중…</StateMessage>}
      {error && <StateMessage error>{error}</StateMessage>}

      {data && (
        <>
          <div className="filter-groups">
            <div className="filter-group">
              <span className="filter-group__label">근거충분성</span>
              <div className="filter-row">
                {(["충분", "부분", "불충분"] as const).map((lv) => (
                  <button
                    key={lv}
                    className={`filter-chip ${evidenceFilter.has(lv) ? "filter-chip--active" : ""}`}
                    onClick={() => setEvidenceFilter((s) => toggle(s, lv))}
                  >
                    {lv} {data.evidenceCounts[lv] ?? 0}
                  </button>
                ))}
              </div>
            </div>
            <div className="filter-group">
              <span className="filter-group__label">시급성</span>
              <div className="filter-row">
                {(["즉시", "중기", "장기"] as const).map((u) => (
                  <button
                    key={u}
                    className={`filter-chip ${urgencyFilter.has(u) ? "filter-chip--active" : ""}`}
                    onClick={() => setUrgencyFilter((s) => toggle(s, u))}
                  >
                    {u} {data.urgencyCounts[u] ?? 0}
                  </button>
                ))}
              </div>
            </div>
            <div className="filter-group">
              <span className="filter-group__label">배점유형</span>
              <div className="filter-row">
                {Object.entries(data.scoringTypeCounts).map(([st, count]) => (
                  <button
                    key={st}
                    className={`filter-chip ${scoringFilter.has(st) ? "filter-chip--active" : ""}`}
                    onClick={() => setScoringFilter((s) => toggle(s, st))}
                  >
                    {st} {count}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <ExhibitCard
            number={6}
            eyebrow="항목 히트맵"
            title={`${data.label} — 득점률 · 근거충분성 매트릭스`}
            subtitle={`${filteredItems.length} / ${data.items.length}개 항목 표시 중`}
            source="esg_diagnosis · 항목당 100점 정규화 기준"
            style={
              domainColor
                ? ({ "--domain-heading-color": domainColor, "--domain-color": domainColor } as CSSProperties)
                : undefined
            }
          >
            <div className="heatmap">
              {filteredItems.map((it) => {
                const score = it.score ?? 0;
                const zero = it.applicable && score === 0;
                // 득점률 50% 이상 = 도메인색 6단계 중 어두운 쪽 → 밝은 텍스트 필요 (§13.4, 색만 도메인색으로 교체)
                const inverse = it.applicable && score >= 50;
                const tierClass = it.applicable && score > 0 ? `domain-tier-${scoreTier(score)}` : "";
                return (
                  <div
                    key={it.code}
                    className={`heatmap__cell ${tierClass} ${zero ? "heatmap__cell--zero" : ""} ${inverse ? "heatmap__cell--inverse" : ""}`}
                    onClick={() => goItem(it.code)}
                  >
                    <span className="heatmap__code">{it.code}</span>
                    <span className="heatmap__name">{it.name}</span>
                    {it.applicable ? (
                      <div className="heatmap__score">
                        <span>{formatNum(score)}/100</span>
                        <EvidenceBadge level={evidenceLevelFromScore(it.score)} />
                      </div>
                    ) : (
                      <span className="heatmap__score" style={{ color: "var(--ink-3)" }}>
                        해당 없음
                      </span>
                    )}
                  </div>
                );
              })}
              {filteredItems.length === 0 && <StateMessage>조건에 맞는 항목이 없습니다.</StateMessage>}
            </div>
          </ExhibitCard>

          {stageItems.length > 0 && (
            <ExhibitCard
              number={7}
              eyebrow="단계형 항목 진척"
              title="현재 단계와 만점 단계 사이 격차가 있는 항목"
              source="esg_diagnosis · [입력]충족단계 / 최대단계수"
              style={domainColor ? ({ "--domain-color": domainColor } as CSSProperties) : undefined}
            >
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>코드</th>
                      <th>항목명</th>
                      <th>현재</th>
                      <th>만점 단계</th>
                      <th>진행</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stageItems.map((it) => {
                      // 만점 단계에 가까울수록(진척률이 높을수록) 채워진 칸이 도메인색 진한 톤을 쓴다.
                      const stageRate = it.maxStageCount ? ((it.currentStage ?? 0) / it.maxStageCount) * 100 : 0;
                      const filledTier = `domain-tier-${scoreTier(stageRate)}`;
                      return (
                        <tr key={it.code} className="clickable" onClick={() => goItem(it.code)}>
                          <td className="mono">{it.code}</td>
                          <td>{it.name}</td>
                          <td>{it.currentStage}단계</td>
                          <td>{it.maxStageCount}단계</td>
                          <td>
                            {Array.from({ length: it.maxStageCount ?? 0 }).map((_, i) => (
                              <span
                                key={i}
                                className={`stage-progress__cell ${i < (it.currentStage ?? 0) ? filledTier : "domain-tier-0"}`}
                              />
                            ))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </ExhibitCard>
          )}

          {activeBucket === "environment" && (
            <ExhibitCard
              number={8}
              eyebrow="감점 이력 타임라인"
              title={data.violations.length ? "환경 법규 위반 이력" : "환경 법규 위반 이력 없음"}
              eyebrowRight={data.isMock && data.violations.length ? <MockBadge>샘플 데이터</MockBadge> : undefined}
              source="환경부 환경정보공개시스템 · 사업보고서 제재 현황 교차 확인 (샘플)"
            >
              {data.violations.length ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {data.violations.map((v, i) => (
                    <div key={i} style={{ display: "flex", gap: 10, borderLeft: "2px solid var(--crit)", paddingLeft: 10 }}>
                      <div style={{ minWidth: 140, fontSize: 12, color: "var(--ink-3)" }} className="mono">
                        {v.date} · {v.site}
                      </div>
                      <div style={{ fontSize: 12.5 }}>
                        {v.title} ({v.law}) — {v.authority} {v.penalty} · {v.type} → 감점 {v.deduction}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <StateMessage>등록된 위반 이력이 없습니다.</StateMessage>
              )}
            </ExhibitCard>
          )}
        </>
      )}
    </div>
  );
}
