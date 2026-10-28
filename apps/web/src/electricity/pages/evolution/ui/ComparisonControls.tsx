import { ComparisonControls as Controls } from '../../../../components/custom/ComparisonControls';
import type { ElectricityState } from '../../../interfaces/electricity-state';
import { formatMarketerLabel } from '../../../lib/electricity-format';

export function ComparisonControls({ electricity }: { electricity: ElectricityState }) {
  return <Controls options={(electricity.marketers.data || [])
    .filter((item) => item.marketer_code !== electricity.marketer && !electricity.comparison.includes(item.marketer_code))
    .map((item) => ({ code: item.marketer_code, title: item.observed_name || 'Sin nombre observado' }))}
    selected={electricity.comparison} disabled={!electricity.enabled || !electricity.codeValid || !electricity.marketers.data}
    onChange={(comparison) => electricity.change({ comparison })}
    labelFor={(code) => formatMarketerLabel(code, electricity.marketers.data)} />;
}
