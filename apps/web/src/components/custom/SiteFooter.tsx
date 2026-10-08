import { Link } from 'react-router';
import { PROJECT_REPOSITORY } from '../../lib/project-links';

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <p>
        Proyecto independiente, sin afiliación con la CNMC, distribuidoras ni comercializadoras.
      </p>
      <nav aria-label="Información del proyecto">
        <Link to="/cookies">Cookies</Link>
        <Link to="/terms">Términos y condiciones</Link>
        <a href={PROJECT_REPOSITORY} target="_blank" rel="noreferrer">GitHub</a>
      </nav>
    </footer>
  );
}
