import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { ChartDimensions } from '../interfaces/chart-dimensions';

export function useChartDimensions() {
  const ref = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<ChartDimensions>({ width: 720, height: 320 });
  const update = useCallback(() => {
    const node = ref.current;
    if (!node) return;
    const style = window.getComputedStyle(node);
    const padding = (Number.parseFloat(style.paddingLeft) || 0) +
      (Number.parseFloat(style.paddingRight) || 0);
    const width = Math.max(280, Math.round(node.clientWidth - padding));
    const chartTop = node.querySelector('.supplies-chart')?.getBoundingClientRect().top;
    const footer = node.closest('.app-shell')?.querySelector('.site-footer');
    const bottom = footer ? Math.min(window.innerHeight, footer.getBoundingClientRect().top) : window.innerHeight;
    const available = bottom - (chartTop ?? node.getBoundingClientRect().top + 110) - 24;
    const height = Math.min(480, Math.max(260, Math.round(available)));
    setDimensions((current) =>
      current.width === width && current.height === height
        ? current
        : { width, height },
    );
  }, []);

  useLayoutEffect(update);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(update);
    observer.observe(node);
    window.addEventListener('resize', update);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [update]);

  return { ref, dimensions };
}
