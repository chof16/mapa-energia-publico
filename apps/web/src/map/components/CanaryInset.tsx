import { useEffect, useRef, useState } from 'react';
import { Map as MapLibreMap } from 'maplibre-gl';
import type { CommunityShare } from '../../market/interfaces/market';
import { marketFill } from '../../market/lib/market-style';
import {
  registerPmtiles,
  canaryBounds,
  SOURCE_ID,
  TILE_URL,
} from '../lib/map-style';
export function CanaryInset({ onClick, items }: { onClick: () => void; items?: CommunityShare[] }) {
  const node = useRef<HTMLSpanElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (ready) mapRef.current?.setPaintProperty('islas', 'fill-color', items ? marketFill(items) : '#e5ebef');
  }, [ready, items]);
  useEffect(() => {
    if (!node.current) return;
    registerPmtiles();
    const map = new MapLibreMap({
      container: node.current,
      bounds: canaryBounds,
      fitBoundsOptions: { padding: 8 },
      interactive: false,
      trackResize: false,
      attributionControl: false,
      renderWorldCopies: false,
      style: {
        version: 8,
        sources: {
          [SOURCE_ID]: {
            type: 'vector',
            url: `pmtiles://${new URL(TILE_URL, window.location.href).href}`,
          },
        },
        layers: [
          {
            id: 'fondo',
            type: 'background',
            paint: { 'background-color': '#fffefa' },
          },
          {
            id: 'islas',
            type: 'fill',
            source: SOURCE_ID,
            'source-layer': 'ccaa',
            filter: ['==', ['get', 'ccaa_ine'], '05'],
            paint: { 'fill-color': '#e5ebef' },
          },
          {
            id: 'costa',
            type: 'line',
            source: SOURCE_ID,
            'source-layer': 'ccaa',
            filter: ['==', ['get', 'ccaa_ine'], '05'],
            paint: { 'line-color': '#3c638a', 'line-width': 1 },
          },
        ],
      },
    });
    mapRef.current = map;
    map.on('load', () => setReady(true));
    const observer = new ResizeObserver(() => {
      if (!node.current?.clientWidth || !node.current.clientHeight) return;
      map.resize();
      map.fitBounds(canaryBounds, { padding: 8, duration: 0 });
      map.redraw();
    });
    observer.observe(node.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <button
      className="canarias-inset"
      onClick={onClick}
      aria-label="Explorar Canarias en el mapa principal"
    >
      <span className="inset-title">
        Canarias <span aria-hidden="true">↗</span>
      </span>
      <span ref={node} className="inset-map" aria-hidden="true" />
      <span className="inset-caption">Recuadro · IGN/CNIG</span>
    </button>
  );
}
