import { ReactNode, useEffect } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUiStore } from '../../store/uiStore';
import clsx from 'clsx';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  const darkMode = useUiStore((state) => state.darkMode);

  // Apply dark class to document root
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Header />
      <div className="flex">
        <Sidebar />
        <main
          className={clsx(
            'flex-1 p-6 transition-all duration-300 min-h-[calc(100vh-4rem)]',
            sidebarOpen ? 'ml-64' : 'ml-16'
          )}
        >
          <div className="max-w-7xl mx-auto">{children}</div>
          <footer className="mt-12 pb-4 text-center">
            <p className="text-xs text-gray-400 dark:text-gray-600">
              {''}
              <a
                href="https://github.com/jwest33"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
              >
                @jwest33
              </a>
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
}
