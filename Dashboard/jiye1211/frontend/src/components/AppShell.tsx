import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate, useParams, useLocation } from "react-router-dom";
import { ConsultPanel } from "./ConsultPanel";
import { CriteriaPanel } from "./CriteriaPanel";
import { CriteriaPanelContext } from "../context/CriteriaPanelContext";
import { useCompanies } from "../hooks/useCompanies";

const RAIL_GROUPS: { label: string; items: { code: string; label: string; path: string; enabled: boolean }[] }[] = [
  {
    label: "진단",
    items: [
      { code: "L1", label: "종합 현황", path: "l1", enabled: true },
      { code: "L2", label: "영역별 진단", path: "l2", enabled: true },
      { code: "L3", label: "항목 상세", path: "l3", enabled: true },
    ],
  },
  {
    label: "분석",
    items: [
      { code: "L4", label: "비교 분석", path: "l4", enabled: true },
      { code: "L5", label: "개선 로드맵", path: "l5", enabled: true },
    ],
  },
  {
    label: "자료",
    items: [
      { code: "L6", label: "증빙 데이터룸", path: "l6", enabled: true },
      { code: "L7", label: "리포트", path: "l7", enabled: true },
    ],
  },
];

export function AppShell() {
  const { company = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { companies } = useCompanies();

  const pathParts = location.pathname.split("/").filter(Boolean); // ["companies", company, screen, sub?]
  const currentScreen = pathParts[2] ?? "l1";
  const itemCode = currentScreen === "l3" ? pathParts[3] : undefined;
  const [consultOpen, setConsultOpen] = useState(currentScreen === "l1");
  const [criteriaOpen, setCriteriaOpen] = useState(false);

  useEffect(() => {
    setConsultOpen(currentScreen === "l1");
  }, [currentScreen]);

  return (
    <CriteriaPanelContext.Provider value={{ open: () => setCriteriaOpen(true) }}>
      <div className="app-shell">
        <header className="topbar">
          <span className="topbar__brand">ESG 통합 진단 센터</span>
          <select
            className="topbar__select"
            value={company}
            onChange={(e) => navigate(`/companies/${encodeURIComponent(e.target.value)}/${currentScreen}`)}
          >
            {companies.map((c) => (
              // c.id(기업코드)는 데이터에는 유지하되 화면 렌더링에서만 뺀다 — 회사명만 표시.
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
          <button className="topbar__link" onClick={() => setCriteriaOpen(true)}>
            평가 기준 보기
          </button>
          <span className="topbar__badge">평가연도 2026</span>
          <span className="topbar__badge">K-ESG v2.0</span>
          <div className="topbar__spacer" />
          <span className="topbar__user">환경안전팀</span>
        </header>

        <div className="app-body" data-consult={consultOpen ? "open" : "collapsed"}>
          <nav className="rail">
            {RAIL_GROUPS.map((group) => (
              <div className="rail__group" key={group.label}>
                <div className="rail__group-label upper-label">{group.label}</div>
                {group.items.map((item) =>
                  item.enabled ? (
                    <Link
                      key={item.code}
                      to={`/companies/${encodeURIComponent(company)}/${item.path}`}
                      className={`rail__item ${currentScreen === item.path ? "rail__item--active" : ""}`}
                    >
                      {item.code} · {item.label}
                    </Link>
                  ) : (
                    <span
                      key={item.code}
                      className="rail__item"
                      style={{ opacity: 0.4, cursor: "not-allowed" }}
                      title="아직 준비되지 않은 화면입니다"
                    >
                      {item.code} · {item.label}
                    </span>
                  )
                )}
              </div>
            ))}
          </nav>

          <main className="main">
            <Outlet />
          </main>

          {/* key={company}: 상단에서 회사를 바꾸면 ConsultPanel을 통째로 새로 마운트해 이전
              대화(turns)를 비운다 — 그대로 두면 다른 회사에 대한 답변이 새 회사 질문의
              [이전 대화] 맥락으로 섞여 들어간다. */}
          <ConsultPanel
            key={company}
            open={consultOpen}
            onToggle={() => setConsultOpen((v) => !v)}
            contextLabel={`${currentScreen.toUpperCase()}${itemCode ? " · " + itemCode : ""} · 2026`}
            company={company}
            itemCode={itemCode}
          />
        </div>

        <CriteriaPanel open={criteriaOpen} onClose={() => setCriteriaOpen(false)} company={company} />
      </div>
    </CriteriaPanelContext.Provider>
  );
}
