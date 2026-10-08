import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { appRoutes } from './app.router';

const appRouter = createBrowserRouter(appRoutes);
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={appRouter} />
    </QueryClientProvider>
  );
}
