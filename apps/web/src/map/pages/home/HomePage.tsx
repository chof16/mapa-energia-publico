import { useMapExplorer } from '../../hooks/useMapExplorer';
import { MapStage } from '../../components/MapStage';
import { MapToolbar } from '../../components/MapToolbar';

export function HomePage() {
  const explorer = useMapExplorer();
  return (
    <section className="workspace" aria-label="Mapa de España">
      <MapToolbar explorer={explorer} />
      <MapStage explorer={explorer} />
    </section>
  );
}
