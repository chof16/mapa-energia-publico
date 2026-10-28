import { CanaryInset } from './CanaryInset';
import { MapLegend } from './MapLegend';
import type { MapExplorer } from '../interfaces/map-explorer';
import { shareColor, missingColor } from '../../electricity/lib/electricity-style';
import { ProvinceEvidence } from '../../distribution/components/ProvinceEvidence';
import { GasProvinceEvidence } from '../../gas/components/GasProvinceEvidence';
import { GasNetworkLegend } from '../../gas/components/GasNetworkLegend';
import { RetryButton } from '../../components/custom/RetryButton';
import { oneDocumentedColor, multipleDocumentedColor, unknownProvinceColor } from '../../distribution/lib/distribution-style';

export function MapStage({ explorer }: { explorer: MapExplorer }) {
  const {
    mapNode,
    mapStatus,
    statusMessage,
    sector,
    showOverview,
    electricity,
    provinceSummary,
    selection,
  } = explorer;
  return (
    <div className="map-wrap" data-evidence={sector === 'gas' || electricity.layer === 'distribution'}>
      <div ref={mapNode} className="map-canvas" />
      {sector === 'electricidad' && electricity.layer === 'distribution' && (
        <ProvinceEvidence selection={selection} />
      )}
      {sector === 'gas' && <GasProvinceEvidence explorer={explorer} />}
      <div className="map-hint" hidden={sector === 'gas' || electricity.layer === 'distribution'}>
        <span className="hint-icon">↗</span> Usa la rueda o los botones para
        acercar
      </div>
      <button
        className="map-home"
        onClick={() => showOverview(false)}
        aria-label="Ver Península, Baleares, Ceuta y Melilla"
      >
        ⌂ <span>Península y Baleares</span>
      </button>
      {mapStatus === 'missing' && (
        <div className="map-message">
          <span className="message-symbol">⌁</span>
          <strong>{statusMessage}</strong>
          <span>
            Comprueba la ruta de los archivos IGN: debe servir un archivo
            PMTiles y su catálogo GeoJSON, no una página HTML.
          </span>
        </div>
      )}
      {mapStatus === 'loading' && (
        <div className="map-loading">
          <span className="loader" />
          {statusMessage}
        </div>
      )}
      <div className="map-bottom-overlays">
        <CanaryInset
          onClick={() => showOverview(true)}
          items={
            electricity.enabled && electricity.layer === 'market'
              ? electricity.communities.data?.items
              : undefined
          }
        />
        <MapLegend>
          {sector === 'gas' ? <GasNetworkLegend query={explorer.gasProvinceSummary} /> : electricity.enabled && electricity.layer === 'market' ? (
            <>
              <strong>Cuota autonómica</strong>
              {[
                [0, '0 %'],
                [0.01, '>0–<5 %'],
                [0.05, '5–<15 %'],
                [0.15, '15–<30 %'],
                [0.3, '≥30 %'],
                [null, 'Sin denominador'],
              ].map(([value, label]) => (
                <span key={String(label)}>
                  <i
                    className="share-swatch"
                    style={{ background: shareColor(value as number | null) }}
                  />
                  {label}
                </span>
              ))}
              <span>
                <i
                  className="share-swatch"
                  style={{ background: missingColor }}
                />
                Sin datos
              </span>
            </>
          ) : sector === 'electricidad' && electricity.layer === 'distribution' ? (
            <>
              <strong>Presencia documentada</strong>
              {provinceSummary.data && !provinceSummary.isError ? (
                <>
                  <span><i className="share-swatch" style={{ background: oneDocumentedColor }} />1 distribuidora</span>
                  <span><i className="share-swatch" style={{ background: multipleDocumentedColor }} />2 o más</span>
                  <span><i className="share-swatch" style={{ background: unknownProvinceColor }} />Sin evidencia (desconocido)</span>
                  <span className="distribution-legend-note">Color = presencia en alguna zona provincial, no cobertura completa ni municipal. Selecciona una provincia para ver fuentes. Revisado el <time dateTime={provinceSummary.data.snapshot_date}>{provinceSummary.data.snapshot_date.split('-').reverse().join('/')}</time>.</span>
                </>
              ) : provinceSummary.isError ? (
                <span className="distribution-legend-note">No se pudo cargar el color de evidencia. <RetryButton loading={provinceSummary.isFetching} onClick={() => void provinceSummary.refetch()}>Reintentar mapa</RetryButton></span>
              ) : (
                <span role="status">Cargando evidencia para el mapa…</span>
              )}
              <span>Límites actuales · <a href="https://www.ign.es/" target="_blank" rel="noreferrer">IGN</a>/<a href="https://www.cnig.es/" target="_blank" rel="noreferrer">CNIG</a></span>
            </>
          ) : (
            <>
              <span className="legend-line legend-ccaa" /> Comunidad{' '}
              <span className="legend-line legend-provincia" /> Provincia{' '}
              <span className="legend-line legend-municipio" /> Municipio{' '}
              <span>Límites actuales · <a href="https://www.ign.es/" target="_blank" rel="noreferrer">IGN</a>/<a href="https://www.cnig.es/" target="_blank" rel="noreferrer">CNIG</a></span>
            </>
          )}
        </MapLegend>
      </div>
    </div>
  );
}
