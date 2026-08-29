import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, UserPlus, ClipboardList, Users,
  RefreshCw, BarChart3, Shield, ChevronLeft, ChevronRight,
  Activity
} from 'lucide-react';
import { useHealth, useEngineInfo } from '@/hooks/use-api';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/intake', icon: UserPlus, label: 'Patient Intake' },
  { to: '/queue', icon: ClipboardList, label: 'Queue' },
  { to: '/patients', icon: Users, label: 'Patients' },
  { to: '/overrides', icon: RefreshCw, label: 'Overrides' },
  { to: '/simulation', icon: BarChart3, label: 'Simulation' },
  { to: '/audit', icon: Shield, label: 'Audit Trail' },
];

export function Layout() {
  const [collapsed, setCollapsed] = React.useState(false);
  const { data: health } = useHealth();
  const { data: engine } = useEngineInfo();

  const engineOk = health?.status === 'ok';

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-16' : 'w-60'} flex flex-col bg-white border-r border-gray-200 transition-all duration-200`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 h-16 border-b border-gray-100">
          <Activity className="h-6 w-6 text-blue-800 flex-shrink-0" />
          {!collapsed && (
            <span className="font-bold text-lg text-gray-900 truncate">
              PatientTriage<span className="text-blue-800">.ai</span>
            </span>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-800'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center h-10 border-t border-gray-100 text-gray-400 hover:text-gray-600"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-lg font-semibold text-gray-800">
            Emergency Department Command Center
          </h1>
          <div className="flex items-center gap-4">
            {/* Engine status */}
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`h-2.5 w-2.5 rounded-full ${engineOk ? 'bg-green-500' : 'bg-red-500'} ${engineOk ? 'animate-pulse' : ''}`}
              />
              <span className={engineOk ? 'text-green-700' : 'text-red-700'}>
                {engineOk ? 'Engine OK' : 'Engine Error'}
              </span>
            </div>
            {engine && (
              <span className="text-xs text-gray-400 hidden md:inline">
                patientTriage v1.0.0-prototype
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>

        {/* Footer */}
        <footer className="h-10 bg-amber-50 border-t border-amber-200 flex items-center justify-center px-4">
          <p className="text-xs text-amber-700 text-center">
            PROTOTYPE — NOT VALIDATED FOR CLINICAL USE | 100% Synthetic Data |
            Model: patientTriage v1.0.0-prototype |
            Jurisdiction: {engine?.jurisdiction || 'India DPDP Act 2023'}
          </p>
        </footer>
      </div>
    </div>
  );
}
