import { SearchSelector } from '../../components/custom/SearchSelector';
import type { MapExplorer } from '../interfaces/map-explorer';
import { LEVELS, LAYER_INFO } from '../lib/map-style';
import { territoryOptions } from '../lib/territories';

export function TerritoryFilters({ explorer }: { explorer: MapExplorer }) {
  const { catalog, catalogError, selection, mapStatus, changeTerritory } = explorer;
  return (
    <fieldset className="hierarchy" disabled={!catalog || mapStatus !== 'ready'}>
      <legend className="visually-hidden">Seleccionar territorio</legend>
      {LEVELS.map((level, index) => {
        const parent = selection.find((item) => item.level === LEVELS[index - 1]);
        return (
          <div className="hierarchy-field" key={level}>
            <label htmlFor={`selector-${level}`}>{LAYER_INFO[level].label}</label>
            <SearchSelector
              id={`selector-${level}`}
              label={LAYER_INFO[level].label}
              key={parent?.code || level}
              options={territoryOptions(catalog, level, selection)}
              value={selection.find((item) => item.level === level)?.code || ''}
              disabled={(index > 0 && !parent) || !catalog || mapStatus !== 'ready'}
              placeholder={
                index === 0
                  ? 'Buscar comunidad'
                  : parent
                    ? index === 1 ? 'Buscar provincia' : 'Buscar municipio'
                    : index === 1
                      ? 'Elige primero una comunidad'
                      : 'Elige primero una provincia'
              }
              onChange={(code) => changeTerritory(level, code)}
            />
          </div>
        );
      })}
      <div className="territory-context">
        {explorer.current ? (
          <>
            <button type="button" onClick={() => explorer.goToBreadcrumb(-1)}>
              Toda España
            </button>
            <strong>{explorer.current.title} · {explorer.current.code}</strong>
          </>
        ) : (
          <span>Busca una zona o selecciónala en el mapa.</span>
        )}
        <span>Mercado: ámbito nacional o autonómico.</span>
      </div>
      {!catalog && (
        <p className="selector-status" role="status">
          {catalogError
            ? 'No se pudieron cargar las zonas. Recarga la página para volver a intentarlo.'
            : 'Cargando comunidades, provincias y municipios…'}
        </p>
      )}
    </fieldset>
  );
}
