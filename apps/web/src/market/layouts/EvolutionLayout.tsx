import { Outlet } from 'react-router';
import { ExplorerHeader } from '../../components/custom/ExplorerHeader';
import { SiteFooter } from '../../components/custom/SiteFooter';
import { useSelectionUrl } from '../../map/hooks/useSelectionUrl';

export function EvolutionLayout() {
  const { sector, explorationLink } = useSelectionUrl(null);
  return (
    <div className="app-shell evolution-shell">
      <ExplorerHeader
        page="evolucion"
        sector={sector}
        explorationLink={explorationLink}
      />
      <main id="exploration-content" className="evolution-content" tabIndex={-1}>
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
