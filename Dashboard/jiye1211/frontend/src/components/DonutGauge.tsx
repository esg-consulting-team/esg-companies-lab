/** 도넛 게이지 — 사양서 §13.4: 반지름 32, 선 두께 8, -90°에서 시작, 채움 --navy, 트랙 --navy-5.
 * r/strokeWidth를 명시적으로 넘기지 않으면 기존 기본값(32/8) 그대로라 기존 호출부(L7 등)는
 * 영향받지 않는다. centerContent를 주면 기본 "N%" 텍스트 대신 2줄(라벨+값)을 링 안에 그린다. */
export function DonutGauge({
  rate,
  size = 76,
  r = 32,
  strokeWidth = 8,
  centerContent,
}: {
  rate: number | null;
  size?: number;
  r?: number;
  strokeWidth?: number;
  /** 링 안쪽 2줄 표시(라벨 작게 위 · 값 크게 아래) — 안 주면 기존처럼 "N%" 한 줄만 표시 */
  centerContent?: { label: string; value: string };
}) {
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
      <circle cx={center} cy={center} r={r} fill="none" stroke="var(--navy-5)" strokeWidth={strokeWidth} />
      {rate !== null && (
        <circle
          cx={center}
          cy={center}
          r={r}
          fill="none"
          stroke="var(--navy)"
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="butt"
          transform={`rotate(-90 ${center} ${center})`}
        />
      )}
      {centerContent ? (
        // 두 줄(라벨+값)을 하나의 <text>+tspan(dy 상대오프셋)으로 그리면 폰트 크기가 다를 때
        // 브라우저마다 기준선 계산이 어긋나 중앙에서 살짝 치우쳐 보인다 — 대신 두 줄을 독립된
        // <text>로 쪼개, 각자 dominantBaseline="middle"로 정확히 센터링한 뒤 절대 y좌표로만 벌린다.
        <>
          <text x={center} y={center - 13} textAnchor="middle" dominantBaseline="middle" className="donut-gauge__center-label">
            {centerContent.label}
          </text>
          <text x={center} y={center + 15} textAnchor="middle" dominantBaseline="middle" className="donut-gauge__center-value">
            {centerContent.value}
          </text>
        </>
      ) : (
        <text x={center} y={center + 4} textAnchor="middle" className="donut-gauge__center">
          {rate === null ? "N/A" : `${(pct * 100).toFixed(0)}%`}
        </text>
      )}
    </svg>
  );
}
