import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";

/** L1 KPI① 가채점 총점 — 도넛 게이지. value는 0~1 사이 비율. */
export default function DonutGauge({ value, size = 72 }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const data = [{ value: pct }];
  return (
    <div className="donut-gauge" style={{ width: size, height: size }}>
      <RadialBarChart
        width={size}
        height={size}
        innerRadius="72%"
        outerRadius="100%"
        data={data}
        startAngle={90}
        endAngle={-270}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
        <RadialBar
          dataKey="value"
          cornerRadius={0}
          fill="var(--navy)"
          background={{ fill: "var(--navy-5)" }}
          isAnimationActive={false}
        />
      </RadialBarChart>
      <div className="donut-gauge-label num">{pct.toFixed(1)}%</div>
    </div>
  );
}
