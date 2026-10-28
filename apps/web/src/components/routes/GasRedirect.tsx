import { Navigate, useSearchParams } from 'react-router';
import { gasMapParams } from '../../gas/lib/navigation';

export function GasRedirect() {
  const [params] = useSearchParams();
  return <Navigate to={`/?${gasMapParams(params)}`} replace />;
}
