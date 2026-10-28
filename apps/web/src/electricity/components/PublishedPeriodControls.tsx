import type { ElectricityState } from '../interfaces/electricity-state';
import { PublishedPeriodControls as PeriodControls } from '../../components/custom/PublishedPeriodControls';

export function PublishedPeriodControls({ electricity, onPeriodChange }: {
  electricity: ElectricityState; onPeriodChange?: () => void;
}) {
  return <PeriodControls periods={electricity.quarters.data} period={electricity.period}
    enabled={electricity.enabled} onPeriodChange={onPeriodChange}
    onChange={(period) => electricity.change({ period })} />;
}
