import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useCompany } from "../state/CompanyContext";

const RAIL_GROUPS = [
  {
    label: "진단",
    items: [
      { to: "/l1", code: "L1", label: "종합 현황", enabled: true },
      { to: "/l2", code: "L2", label: "영역별 진단", enabled: true },
      { to: "/l3", code: "L3", label: "항목 상세", enabled: true },
    ],
  },
  {
    label: "분석",
    items: [
      { to: "/l4", code: "L4", label: "비교 분석", enabled: true },
      { to: "/l5", code: "L5", label: "개선 로드맵", enabled: true },
    ],
  },
  {
    label: "자료",
    items: [
      { to: "/l6", code: "L6", label: "증빙 데이터룸", enabled: true },
      { to: "/l7", code: "L7", label: "리포트", enabled: true },
    ],
  },
];

export default function AppShell() {
  const { companies, company, setCompany, loading } = useCompany();
  const [aiOpen, setAiOpen] = useState(true);
  const location = useLocation();
  const currentCode = location.pathname.split("/")[1]?.toUpperCase();

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="app-topbar-left">
          <span className="app-topbar-brand">ESG 진단 콘솔</span>
          {!loading && (
            <select
              data-testid="company-select"
              value={company || ""}
              onChange={(e) => setCompany(e.target.value)}
            >
              {companies.map((c) => (
                <option key={c.company} value={c.company}>
                  {c.company} {c.stock_code ? `${c.stock_code}` : ""}
                </option>
              ))}
            </select>
          )}
          <select disabled defaultValue="2025">
            <option value="2025">평가연도 2025</option>
          </select>
          <span className="upper-label">K-ESG v2.0</span>
        </div>
        <div className="app-topbar-right">
          <span className="provisional-badge">가채점 · 검수완료</span>
        </div>
      </header>

      <nav className="rail">
        {RAIL_GROUPS.map((group) => (
          <div className="rail-group" key={group.label}>
            <div className="rail-group-label">{group.label}</div>
            {group.items.map((item) =>
              item.enabled ? (
                <NavLink
                  key={item.code}
                  to={item.to}
                  className={({ isActive }) => `rail-item${isActive ? " active" : ""}`}
                >
                  {item.code} · {item.label}
                </NavLink>
              ) : (
                <span key={item.code} className="rail-item disabled" title="다음 단계에서 제공 예정">
                  {item.code} · {item.label}
                </span>
              )
            )}
          </div>
        ))}
      </nav>

      <main className="app-main">
        <Outlet />
      </main>

      {aiOpen ? (
        <aside className="ai-panel">
          <div className="ai-panel-header">
            <span>
              <strong>AI 상담</strong> <span className="ai-context-badge">{currentCode} · 2025</span>
            </span>
            <button className="ai-close-btn" onClick={() => setAiOpen(false)} aria-label="닫기">
              ✕
            </button>
          </div>
          <p style={{ fontSize: 12.5 }}>
            항목을 선택하면 해당 화면 컨텍스트를 기반으로 근거를 인용해 답할 예정입니다. (확장 단계 F5 —
            이번 릴리스에서는 준비 중)
          </p>
          <div className="ai-panel-footer">
            답변은 적재된 자사 문서에서만 생성됩니다. 근거를 찾지 못하면 추정하지 않고 필요한 증빙을
            안내합니다.
          </div>
        </aside>
      ) : (
        <div className="ai-strip" onClick={() => setAiOpen(true)}>
          <span className="ai-strip-label">AI 상담</span>
        </div>
      )}
    </div>
  );
}
