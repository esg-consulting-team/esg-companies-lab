import { useState } from "react";

/** hover 시 content를 말풍선으로 보여주는 범용 툴팁 래퍼. content가 없으면 children만 렌더링. */
export default function Tooltip({ content, children, className = "" }) {
  const [show, setShow] = useState(false);
  if (!content) return children;
  return (
    <span
      className={`tooltip-wrap ${className}`}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      tabIndex={0}
    >
      {children}
      {show && <span className="tooltip-bubble">{content}</span>}
    </span>
  );
}
