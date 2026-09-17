export default function ExhibitCard({ number, tag, title, subtitle, source, children }) {
  return (
    <div className="exhibit">
      <div className="exhibit-eyebrow">
        <span className="exhibit-number">EXHIBIT {number}</span>
        {tag && <span className="exhibit-tag mono">{tag}</span>}
      </div>
      <div className="exhibit-title serif">{title}</div>
      {subtitle && <div className="exhibit-subtitle">{subtitle}</div>}
      <hr className="exhibit-rule" />
      <div>{children}</div>
      {source && (
        <>
          <hr className="exhibit-rule" />
          <div className="exhibit-source">출처: {source}</div>
        </>
      )}
    </div>
  );
}
