import { Outlet } from 'react-router';
import { ExplorerHeader } from '../../components/custom/ExplorerHeader';
import { SiteFooter } from '../../components/custom/SiteFooter';
import { useSelectionUrl } from '../hooks/useSelectionUrl';

export function MapLayout() {
  const { sector, explorationLink } = useSelectionUrl(null);
  return (
    <div className="app-shell">
      <ExplorerHeader
        page="mapa"
        sector={sector}
        explorationLink={explorationLink}
      />
      <main id="exploration-content" className="map-content" tabIndex={-1}>
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
