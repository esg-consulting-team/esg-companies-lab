import { Cell, Pie, PieChart } from "recharts";

const COLORS = { 즉시: "var(--crit)", 중기: "var(--warn)", 장기: "var(--ink-3)" };
const ORDER = ["즉시", "중기", "장기"];

/** L1 Exhibit4 — 시급성 분포 도넛 + 범례. counts = {즉시, 중기, 장기} */
export default function UrgencyDonut({ counts, size = 128 }) {
  const total = ORDER.reduce((s, k) => s + (counts[k] || 0), 0);
  const data = ORDER.map((name) => ({ name, value: counts[name] || 0 }));

  return (
    <div className="urgency-donut">
      <div className="urgency-donut-chart" style={{ width: size, height: size }}>
        <PieChart width={size} height={size}>
          <Pie
            data={data}
            dataKey="value"
            innerRadius={size * 0.32}
            outerRadius={size * 0.48}
            startAngle={90}
            endAngle={-270}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={COLORS[d.name]} />
            ))}
          </Pie>
        </PieChart>
        <div className="urgency-donut-center num">{total}건</div>
      </div>
      <div className="urgency-donut-legend">
        {data.map((d) => (
          <div className="urgency-donut-legend-row" key={d.name}>
            <span className="legend-dot" style={{ background: COLORS[d.name] }} />
            <span>{d.name}</span>
            <span className="num">
              {d.value}건 ({total ? Math.round((d.value / total) * 100) : 0}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
