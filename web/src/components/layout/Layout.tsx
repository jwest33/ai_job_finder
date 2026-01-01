import { ReactNode } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUiStore } from '../../store/uiStore';
import clsx from 'clsx';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="flex">
        <Sidebar />
        <main
          className={clsx(
            'flex-1 p-6 transition-all duration-300',
            sidebarOpen ? 'ml-64' : 'ml-16'
          )}
        >
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
