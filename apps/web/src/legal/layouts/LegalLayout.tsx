import { Link, Outlet, useLocation } from 'react-router';
import { EnergyBrand } from '../../components/custom/EnergyBrand';
import { SiteFooter } from '../../components/custom/SiteFooter';
import '../styles.css';

export function LegalLayout() {
  const { pathname } = useLocation();
  return (
    <div className="app-shell legal-shell">
      <header className="legal-header">
        <a className="skip-link" href="#legal-content">Saltar al contenido</a>
        <EnergyBrand to="/" />
      </header>
      <main
        id="legal-content"
        className="legal-content"
        key={pathname}
        tabIndex={-1}
        ref={(node) => { node?.focus(); }}
      >
        <Link className="legal-back" to="/">
          <span aria-hidden="true">←</span>
          Back to map
        </Link>
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
