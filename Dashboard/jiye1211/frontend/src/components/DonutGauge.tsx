/** 도넛 게이지 — 사양서 §13.4: 반지름 32, 선 두께 8, -90°에서 시작, 채움 --navy, 트랙 --navy-5 */
export function DonutGauge({ rate, size = 76 }: { rate: number | null; size?: number }) {
  const r = 32;
  const stroke = 8;
  const c = 2 * Math.PI * r;
  const pct = rate ?? 0;
  const dash = c * pct;
  const center = size / 2;

  return (
    <svg
      className="donut-gauge__figure"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={rate === null ? "데이터 없음" : `달성률 ${(pct * 100).toFixed(1)}%`}
    >
      <circle cx={center} cy={center} r={r} fill="none" stroke="var(--navy-5)" strokeWidth={stroke} />
      {rate !== null && (
        <circle
          cx={center}
          cy={center}
          r={r}
          fill="none"
          stroke="var(--navy)"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="butt"
          transform={`rotate(-90 ${center} ${center})`}
        />
      )}
      <text x={center} y={center + 4} textAnchor="middle" className="donut-gauge__center">
        {rate === null ? "N/A" : `${(pct * 100).toFixed(0)}%`}
      </text>
    </svg>
  );
}
