import { Link } from 'react-router';

export function EnergyBrand({ to }: { to: string }) {
  return (
    <Link className="brand" to={to} aria-label="Red energía, mapa de España">
      <span className="brand-mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>
        <strong>red</strong>
        <span className="brand-light"> energía</span>
        <small>ESPAÑA · DATOS ABIERTOS</small>
      </span>
    </Link>
  );
}
