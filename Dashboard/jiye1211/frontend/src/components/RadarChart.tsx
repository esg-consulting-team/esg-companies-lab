/** 레이더(스파이더) 차트 — 자사 vs 벤치마킹사 다축 비교 전용.
 * 비교 계열은 §13.4 규칙대로 네이비 명도 단계로만 구분한다(무지개색 금지). */
export interface RadarAxis {
  key: string;
  label: string;
}

export interface RadarSeries {
  label: string;
  color: string;
  /** true면 자사 — 채움 + 굵은 선으로 강조, false면 벤치마킹사 — 선만 */
  emphasize?: boolean;
  values: Record<string, number | null>;
}

const SIZE = 240;
const CENTER = SIZE / 2;
const MAX_RADIUS = 82;
const GRID_LEVELS = [25, 50, 75, 100];

function axisPoint(index: number, count: number, radius: number): [number, number] {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  return [CENTER + radius * Math.cos(angle), CENTER + radius * Math.sin(angle)];
}

function polygonPoints(count: number, radius: number): string {
  return Array.from({ length: count }, (_, i) => axisPoint(i, count, radius).join(",")).join(" ");
}

export function RadarChart({ axes, series }: { axes: RadarAxis[]; series: RadarSeries[] }) {
  const n = axes.length;
  if (n < 3) return null;

  return (
    <div className="radar-chart">
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        style={{ overflow: "visible" }}
        role="img"
        aria-label="자사 vs 벤치마킹군 레이더 차트"
      >
        {GRID_LEVELS.map((lvl) => (
          <polygon
            key={lvl}
            points={polygonPoints(n, (MAX_RADIUS * lvl) / 100)}
            fill="none"
            stroke="var(--rule-mid)"
            strokeWidth={1}
          />
        ))}

        {axes.map((axis, i) => {
          const [x, y] = axisPoint(i, n, MAX_RADIUS);
          return <line key={axis.key} x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="var(--rule-mid)" strokeWidth={1} />;
        })}

        {series.map((s) => {
          const points = axes
            .map((axis, i) => {
              const raw = s.values[axis.key];
              const value = raw === null || raw === undefined ? 0 : Math.max(0, Math.min(100, raw));
              const [x, y] = axisPoint(i, n, (MAX_RADIUS * value) / 100);
              return `${x},${y}`;
            })
            .join(" ");
          return (
            <polygon
              key={s.label}
              points={points}
              fill={s.emphasize ? s.color : "none"}
              fillOpacity={s.emphasize ? 0.12 : 0}
              stroke={s.color}
              strokeWidth={s.emphasize ? 2.5 : 1.5}
            />
          );
        })}

        {axes.map((axis, i) => {
          const [x, y] = axisPoint(i, n, MAX_RADIUS + 26);
          const anchor = Math.abs(x - CENTER) < 4 ? "middle" : x > CENTER ? "start" : "end";
          return (
            <text key={axis.key} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className="radar-chart__axis-label">
              {axis.label}
            </text>
          );
        })}
      </svg>

      <div className="radar-chart__legend">
        {series.map((s) => (
          <span className="radar-chart__legend-item" key={s.label}>
            <span className="radar-chart__legend-swatch" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
