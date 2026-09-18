import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useCompany } from "../state/CompanyContext";

const FORMATS = [
  { key: "xlsx", label: "XLSX", note: "채점표 원본" },
  { key: "pdf", label: "PDF", note: "경영진 보고 (준비 중)" },
  { key: "pptx", label: "PPTX", note: "사내 발표 (준비 중)" },
];

export default function L7Report() {
  const { company } = useCompany();
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const [checked, setChecked] = useState(() => new Set());
  const [format, setFormat] = useState("xlsx");
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (!company) return;
    setConfig(null);
    setError(null);
    api
      .reportConfig(company)
      .then((cfg) => {
        setConfig(cfg);
        setChecked(new Set(cfg.sections.filter((s) => s.no !== "부록").map((s) => s.no)));
      })
      .catch((err) => setError(err.message));
  }, [company]);

  const totalPages = useMemo(() => {
    if (!config) return 0;
    return config.sections.filter((s) => checked.has(s.no)).reduce((sum, s) => sum + s.pages, 0);
  }, [config, checked]);

  const toggle = (no) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(no)) next.delete(no);
      else next.add(no);
      return next;
    });
  };

  const handleExport = async () => {
    setStatus({ kind: "busy", message: "생성 중…" });
    try {
      const blob = await api.exportReport(company, format, Array.from(checked));
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${company}_esg_export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus({ kind: "ok", message: `${format.toUpperCase()} 다운로드 완료` });
      api.reportConfig(company).then(setConfig).catch(() => {});
    } catch (err) {
      setStatus({ kind: "error", message: err.message });
    }
  };

  if (error) return <div className="empty-state">불러오기 실패: {error}</div>;
  if (!config) return <div className="loading">불러오는 중…</div>;

  return (
    <div className="report-layout">
      <div className="exhibit">
        <div className="exhibit-title serif">포함 섹션</div>
        <div className="exhibit-subtitle">체크 해제한 장은 목차와 페이지 번호에서 함께 빠집니다.</div>
        <hr className="exhibit-rule" />
        {config.sections.map((s) => (
          <div className="section-row" key={s.no}>
            <input type="checkbox" checked={checked.has(s.no)} onChange={() => toggle(s.no)} />
            <span className="mono">{s.no}</span>
            <span>{s.title}</span>
            <span className="pages num">{s.pages}p</span>
          </div>
        ))}
        <hr className="exhibit-rule" />
        <div style={{ fontSize: 12.5 }}>
          선택 합계 <strong className="num">{totalPages}p</strong>
        </div>
      </div>

      <div>
        <div className="exhibit">
          <div className="exhibit-title serif">출력 형식</div>
          <div className="exhibit-subtitle">
            XLSX는 현재 항목별 채점 데이터를 실제로 내려받습니다. PDF·PPTX는 확장 단계(F6-04)에서 제공됩니다.
          </div>
          <hr className="exhibit-rule" />
          <div className="format-choice">
            {FORMATS.map((f) => (
              <button
                key={f.key}
                className={`chip${format === f.key ? " active" : ""}`}
                onClick={() => setFormat(f.key)}
                title={f.note}
              >
                {f.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleExport}
            disabled={checked.size === 0 || status?.kind === "busy"}
            style={{
              border: "1px solid var(--navy)",
              background: "var(--navy)",
              color: "var(--paper)",
              padding: "8px 16px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            리포트 생성
          </button>
          {status && (
            <div
              style={{
                marginTop: 10,
                fontSize: 12,
                color: status.kind === "error" ? "var(--crit)" : "var(--ink-2)",
              }}
            >
              {status.message}
            </div>
          )}
        </div>

        <div className="exhibit">
          <div className="exhibit-title serif">생성 이력</div>
          <hr className="exhibit-rule" />
          {config.export_history.length === 0 ? (
            <div className="empty-note">아직 생성 이력이 없습니다.</div>
          ) : (
            <table className="plain">
              <thead>
                <tr>
                  <th>일시</th>
                  <th>형식</th>
                  <th className="num">분량</th>
                </tr>
              </thead>
              <tbody>
                {config.export_history.map((h, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: 11.5 }}>{new Date(h.created_at).toLocaleString("ko-KR")}</td>
                    <td className="mono">{h.format.toUpperCase()}</td>
                    <td className="num mono">{h.page_estimate ?? "—"}p</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
