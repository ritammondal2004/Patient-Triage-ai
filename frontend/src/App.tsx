import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from '@/components/layout/Layout';
import { DashboardPage } from '@/pages/DashboardPage';
import { IntakePage } from '@/pages/IntakePage';
import { QueuePage } from '@/pages/QueuePage';
import { PatientsPage } from '@/pages/PatientsPage';
import { OverridesPage } from '@/pages/OverridesPage';
import { SimulationPage } from '@/pages/SimulationPage';
import { AuditPage } from '@/pages/AuditPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="intake" element={<IntakePage />} />
            <Route path="queue" element={<QueuePage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="overrides" element={<OverridesPage />} />
            <Route path="simulation" element={<SimulationPage />} />
            <Route path="audit" element={<AuditPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
