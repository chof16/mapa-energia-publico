// Web application navigation header.
import { Link } from 'react-router';
import { EnergyBrand } from './EnergyBrand';
import type {
  Exploration,
  ExplorationPage,
  EnergySector,
} from '../../lib/exploration-url.ts';

interface ExplorerHeaderProps {
  page: ExplorationPage;
  sector: EnergySector;
  explorationLink: (changes: Partial<Exploration> & { page?: ExplorationPage }) => string;
}

export function ExplorerHeader({
  page,
  sector,
  explorationLink,
}: ExplorerHeaderProps) {
  return (
    <header className="topbar">
      <a className="skip-link" href="#exploration-content">
        Saltar al contenido
      </a>
      <EnergyBrand to={explorationLink({ page: 'mapa' })} />
      <nav className="main-nav" aria-label="Navegación principal">
        <Link
          to={explorationLink({ page: 'mapa' })}
          aria-current={page === 'mapa' ? 'page' : undefined}
        >
          Mapa
        </Link>
        <Link
          to={explorationLink({ page: 'evolucion' })}
          aria-current={page === 'evolucion' ? 'page' : undefined}
        >
          Evolución de comercializadoras
        </Link>
        <Link
          to={explorationLink({ page: 'referencia' })}
          aria-current={page === 'referencia' ? 'page' : undefined}
        >
          Tarifa regulada
        </Link>
      </nav>
      <nav className="sector-switch" aria-label="Sector energético">
        <Link
          to={explorationLink({ sector: 'electricidad' })}
          aria-current={sector === 'electricidad' ? 'true' : undefined}
        >
          Electricidad
        </Link>
        <Link
          to={explorationLink({ sector: 'gas' })}
          aria-current={sector === 'gas' ? 'true' : undefined}
        >
          Gas <span className="sector-soon">Próximamente</span>
        </Link>
      </nav>
    </header>
  );
}
