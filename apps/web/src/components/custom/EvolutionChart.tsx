import { ChartAxes } from './ChartAxes';

export const evolutionColors = ['#185eaa', '#b24c22', '#6663a8', '#98620c'];
export const quarterIndex = (period: string) => Number(period.slice(0, 4)) * 4 + Number(period.at(-1));

// Sector adapters provide only drawable values. Missing or bounded observations stay gaps.
export function EvolutionChart({ periods, series, width, height, max, share, label, valueLabel, left, right, bottom, x, y, pointLabel, onActive }: {
  periods: string[]; series: { code: string; values: Map<string, { value: number | null | undefined; continuity?: string }> }[];
  width: number; height: number; max: number; share: boolean; label: string; valueLabel?: string;
  left?: number; right?: number; bottom?: number;
  x: (period: string) => number; y: (value: number) => number;
  pointLabel: (code: string, period: string, value: number) => string;
  onActive: (point: { code: string; period: string } | null) => void;
}) {
  return <svg className="supplies-chart" viewBox={`0 0 ${width} ${height}`} style={{ height }} role="img" aria-label={label}>
    <desc>Una línea por comercializadora; los huecos indican que no se puede mostrar un valor.</desc>
    <ChartAxes periods={periods} max={max} share={share} width={width} height={height} left={left} right={right} bottom={bottom} x={x} y={y} valueLabel={valueLabel} />
    {series.map((item, index) => {
      const segments: string[] = [];
      let previous: number | null = null;
      let previousContinuity: string | undefined;
      for (const period of periods) {
        const value = item.values.get(period)?.value;
        if (value == null) { previous = null; continue; }
        const coordinates = `${x(period)},${y(value)}`;
        const continuity = item.values.get(period)?.continuity;
        if (previous !== null && quarterIndex(period) === previous + 1 && continuity === previousContinuity) segments[segments.length - 1] += ` ${coordinates}`;
        else segments.push(coordinates);
        previous = quarterIndex(period);
        previousContinuity = continuity;
      }
      return <g key={item.code}>
        {segments.map((points, segment) => <polyline key={segment} points={points} fill="none" stroke={evolutionColors[index]} strokeWidth="2.5" strokeDasharray={index ? `${8 - index} ${index + 2}` : undefined} />)}
        {periods.map((period) => {
          const value = item.values.get(period)?.value;
          if (value == null) return null;
          const activate = () => onActive({ code: item.code, period });
          return <g key={period}>
            <circle cx={x(period)} cy={y(value)} r="3" fill={evolutionColors[index]} />
            <circle cx={x(period)} cy={y(value)} r="9" fill="transparent" tabIndex={0} role="button" className="chart-point-target"
              aria-label={pointLabel(item.code, period, value)} onMouseEnter={activate} onMouseLeave={() => onActive(null)}
              onFocus={activate} onBlur={() => onActive(null)} onClick={activate} onKeyDown={(event) => {
                if (event.key === 'Escape') onActive(null);
                if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
              }} />
          </g>;
        })}
      </g>;
    })}
  </svg>;
}
