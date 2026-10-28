import { CompanyDetails } from '../../components/custom/CompanyDetails';
import { SearchSelector } from '../../components/custom/SearchSelector';
import { RetryButton } from '../../components/custom/RetryButton';
import { ElectricitySummary } from '../../electricity/components/ElectricitySummary';
import { ElectricitySource } from '../../electricity/components/ElectricitySource';
import { formatQuarter } from '../../electricity/lib/electricity-format';
import type { MapExplorer } from '../interfaces/map-explorer';

export function MapCompanySearch({ explorer }: { explorer: MapExplorer }) {
  const { electricity, community } = explorer;
  const query = community ? electricity.areaMarketers : electricity.marketers;
  const items = [...(query.data || [])].sort(
    (a, b) => b.supplies - a.supplies || a.marketer_code.localeCompare(b.marketer_code),
  );
  const selected = items.find((item) => item.marketer_code === electricity.marketer);
  const quarter = electricity.quarters.data?.find(
    (item) => item.period === electricity.period,
  );
  const options = items.map((item) => ({
    code: item.marketer_code,
    title: item.observed_name || 'Sin nombre observado',
  }));
  if (electricity.codeValid && !selected) {
    options.unshift({
      code: electricity.marketer,
      title:
        electricity.marketers.data?.find((item) => item.marketer_code === electricity.marketer)
          ?.observed_name || 'Código seleccionado (sin nombre observado)',
    });
  }

  return <CompanyDetails selectionKey={electricity.marketer}
    enabled={electricity.enabled && electricity.published && !!quarter}
    label={electricity.codeValid ? 'Cuotas y fuente' : 'Fuente CNMC'}
    search={<>
      <label htmlFor="electricity-marketer">Comercializadora · código R2</label>
      <SearchSelector id="electricity-marketer" label="Comercializadora · código R2"
        value={electricity.marketer} options={options}
        disabled={!electricity.enabled || !electricity.published || !query.data}
        placeholder="Buscar empresa y ver suministros" describedBy="company-search-context"
        optionDetail={(code) => {
          const item = items.find((entry) => entry.marketer_code === code);
          return item ? `${item.supplies.toLocaleString('es-ES')} suministros` : 'Sin observaciones en este ámbito';
        }}
        onChange={(marketer) => electricity.change({ marketer, ...(marketer ? { layer: 'market' } : {}) })} />
    </>}
    summary={<>{community?.title || 'España'} · {formatQuarter(electricity.period)}
      {electricity.enabled && electricity.published && query.isSuccess && <strong>
        {selected ? `${selected.supplies.toLocaleString('es-ES')} suministros`
          : electricity.marketer ? 'Sin observaciones en este ámbito' : `${items.length} comercializadoras · más suministros primero`}
      </strong>}
    </>}
    status={<>
      {electricity.enabled && electricity.published && community && query.isPending &&
        <p role="status" className="electricity-note">Cargando suministros de la comunidad…</p>}
      {electricity.enabled && electricity.published && community && (query.isError || (query.isFetching && query.errorUpdatedAt > 0 && !query.data)) &&
        <p role="alert" className="electricity-note">No se pudieron cargar las comercializadoras de la zona.{' '}
          <RetryButton loading={query.isFetching} onClick={() => void query.refetch()}>Reintentar comercializadoras</RetryButton></p>}
    </>}>
    {electricity.codeValid ? <ElectricitySummary electricity={electricity} catalog={explorer.catalog}
      community={community?.code || null} onSelectCommunity={(code) => explorer.changeTerritory('ccaa', code)} />
      : quarter && <><p className="electricity-note">Suministros de España o de toda la comunidad autónoma, también al seleccionar una provincia o municipio. No indican cobertura de distribuidoras.</p>
        <ElectricitySource source={quarter} revision={quarter.metadata_modified} /></>}
  </CompanyDetails>;
}
