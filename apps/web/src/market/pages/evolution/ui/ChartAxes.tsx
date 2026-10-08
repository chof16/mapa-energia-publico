export function ChartAxes({
  periods,
  max,
  share = false,
  left = 65,
  width,
  height,
  x,
  y,
}: {
  periods: string[];
  max: number;
  share?: boolean;
  left?: number;
  width: number;
  height: number;
  x: (period: string) => number;
  y: (value: number) => number;
}) {
  const values = [
    ...new Set(
      [0, 0.25, 0.5, 0.75, 1].map((ratio) =>
        share ? max * ratio : Math.round(max * ratio),
      ),
    ),
  ];
  const ticks = [
    ...new Set(
      Array.from(
        { length: Math.min(width < 480 ? 3 : width < 800 ? 5 : 7, periods.length) },
        (_, index) =>
          periods[
            Math.round(
              (index * (periods.length - 1)) /
                Math.max(1, Math.min(width < 480 ? 3 : width < 800 ? 5 : 7, periods.length) - 1),
            )
          ]!,
      ),
    ),
  ];
  return (
    <g className="chart-axes">
      <text x={left} y="20" className="chart-axis-title">
        {share ? 'Cuota de suministros (%)' : 'CUPS (suministros)'}
      </text>
      {values.map((value) => (
        <g key={value}>
          <line
            x1={left}
            x2={width - 45}
            y1={y(value)}
            y2={y(value)}
            stroke="#dce4ec"
          />
          <text x={left - 7} y={y(value) + 4} textAnchor="end">
            {share
              ? `${(value * 100).toLocaleString('es-ES', { maximumFractionDigits: 1 })} %`
              : value.toLocaleString('es-ES')}
          </text>
        </g>
      ))}
      <line x1={left} x2={width - 45} y1={height - 75} y2={height - 75} stroke="#819bb3" />
      {ticks.map((period, index) => (
        <g
          key={period}
          className={
            index % 2 && index !== ticks.length - 1
              ? 'axis-tick-secondary'
              : undefined
          }
        >
          <line
            x1={x(period)}
            x2={x(period)}
            y1={height - 75}
            y2={height - 69}
            stroke="#819bb3"
          />
          <text
            x={x(period)}
            y={height - 50}
            textAnchor={
              index === 0
                ? 'start'
                : index === ticks.length - 1
                  ? 'end'
                  : 'middle'
            }
          >
            T{period.at(-1)} {period.slice(0, 4)}
          </text>
        </g>
      ))}
      <text
        x={(left + width - 45) / 2}
        y={height - 15}
        textAnchor="middle"
        className="chart-axis-title"
      >
        Trimestre y año
      </text>
    </g>
  );
}
