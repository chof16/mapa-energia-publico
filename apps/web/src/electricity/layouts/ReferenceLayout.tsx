import { Outlet } from 'react-router';
import { ExplorerHeader } from '../../components/custom/ExplorerHeader';
import { SiteFooter } from '../../components/custom/SiteFooter';
import { useSelectionUrl } from '../../map/hooks/useSelectionUrl';

export function ReferenceLayout() {
  const { sector, explorationLink } = useSelectionUrl(null);
  return (
    <div className="app-shell reference-shell">
      <ExplorerHeader page="referencia" sector={sector} explorationLink={explorationLink} />
      <main id="exploration-content" className="reference-content" tabIndex={-1}>
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
