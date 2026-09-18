import { useState } from "react";
import { useCompany } from "../state/CompanyContext";

/** 시급성 배지 옆 "?" — 클릭하면 회사별 시급성 판단기준을 팝오버로 보여준다.
 * 등록된 기준이 없는 회사(레벨)는 "?" 자체를 렌더링하지 않는다. */
export default function UrgencyHelp({ level }) {
  const { urgencyCriteria } = useCompany();
  const [open, setOpen] = useState(false);
  const criteria = urgencyCriteria?.[level];
  if (!criteria) return null;

  return (
    <span className="urgency-help">
      <button
        type="button"
        className="urgency-help-btn"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        aria-label={`${level} 시급성 판단기준 보기`}
      >
        ?
      </button>
      {open && (
        <>
          <div className="urgency-help-backdrop" onClick={() => setOpen(false)} />
          <div className="urgency-help-popover">
            <div className="urgency-help-title">{level} 판단기준</div>
            <div className="urgency-help-body">{criteria}</div>
          </div>
        </>
      )}
    </span>
  );
}
