import { vi } from 'vitest';
import type { LayerSpecification, MapOptions } from 'maplibre-gl';

// Model the imperative WebGL boundary; all React components, hooks and styles stay real.
export class MapBoundary {
  static instances: MapBoundary[] = [];
  readonly options: MapOptions;
  readonly layers = new Map<string, LayerSpecification>();
  readonly handlers = new Map<string, (event: unknown) => void>();
  readonly setData = vi.fn();
  readonly setFeatureState = vi.fn();
  readonly setPaintProperty = vi.fn();
  readonly setLayoutProperty = vi.fn();
  readonly resize = vi.fn();
  readonly redraw = vi.fn();
  readonly addControl = vi.fn();
  readonly remove = vi.fn(() => {
    this.removed = true;
  });
  features: unknown[] = [];
  private removed = false;
  private center = { lng: -3.7, lat: 40.2 };

  constructor(options: MapOptions) {
    this.options = options;
    MapBoundary.instances.push(this);
  }

  on(name: string, callback: (event: unknown) => void) {
    this.handlers.set(name, callback);
    if (name === 'load')
      queueMicrotask(() => {
        if (!this.removed) callback({});
      });
    return this;
  }

  addLayer(layer: LayerSpecification) {
    this.layers.set(layer.id, layer);
  }
  getLayer(id: string) {
    return this.layers.get(id);
  }
  getSource() {
    return { setData: this.setData };
  }
  getContainer() {
    return this.options.container as HTMLElement;
  }
  getCenter() {
    return this.center;
  }
  queryRenderedFeatures() {
    return this.features;
  }
  fitBounds = vi.fn((bounds: [[number, number], [number, number]]) => {
    this.center = {
      lng: (bounds[0][0] + bounds[1][0]) / 2,
      lat: (bounds[0][1] + bounds[1][1]) / 2,
    };
    this.handlers.get('moveend')?.({});
  });
}
