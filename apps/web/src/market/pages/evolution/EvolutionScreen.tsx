import { RetryButton } from '../../../components/custom/RetryButton';
import { useTerritoryCatalog } from '../../../map/hooks/useTerritoryCatalog';
import { useSelectionUrl } from '../../../map/hooks/useSelectionUrl';
import { useMarket } from '../../hooks/useMarket';
import { MarketControls } from '../../components/MarketControls';
import { ChoiceSelector } from '../../../components/custom/ChoiceSelector';
import { EvolutionPage } from './EvolutionPage';
import { ComparisonControls } from './ui/ComparisonControls';

export function EvolutionScreen() {
  const catalog = useTerritoryCatalog();
  const { selection, sector, navigate } = useSelectionUrl(catalog.data || null);
  const community = selection[0];
  const market = useMarket(
    sector === 'electricidad',
    true,
    community?.code || null,
  );
  const areaFilter = (
    <ChoiceSelector
      id="evolution-area"
      className="evolution-area"
      label="Ámbito territorial"
      value={community?.code || ''}
      disabled={!catalog.data}
      onChange={(code) => {
        const next = catalog.data?.indexes.ccaa.get(code);
        navigate(next ? [next] : []);
      }}
      options={[
        { code: '', title: 'España' },
        ...(catalog.data?.lists.ccaa.map((item) => ({
          code: item.code,
          title: item.title,
        })) || []),
      ]}
    />
  );
  return (
    <>
      <div className="evolution-toolbar">
        <div className="toolbar-title">
          <h1>Evolución de comercializadoras</h1>
          <p>Explora la serie histórica y compara hasta cuatro comercializadoras.</p>
        </div>
        <MarketControls market={market} showPeriod={false} />
        <ComparisonControls market={market} />
        {(catalog.isError ||
          (catalog.isFetching &&
            catalog.errorUpdatedAt > 0 &&
            !catalog.data)) && (
          <p role="alert">
            No se pudo cargar el catálogo territorial.{' '}
            <RetryButton
              loading={catalog.isFetching}
              onClick={() => void catalog.refetch()}
            >
              Reintentar catálogo
            </RetryButton>
          </p>
        )}
      </div>
      {catalog.data && (
        <EvolutionPage
          market={market}
          area={community?.title || 'España'}
          areaFilter={areaFilter}
        />
      )}
      {catalog.isPending && <p role="status">Cargando territorios…</p>}
    </>
  );
}
