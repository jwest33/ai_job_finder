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
            'flex-1 p-6 pb-12 transition-all duration-300 min-h-[calc(100vh-4rem)] relative',
            sidebarOpen ? 'ml-64' : 'ml-16'
          )}
        >
          <div className="max-w-7xl mx-auto">{children}</div>
          <footer className="absolute bottom-0 left-0 right-0 pb-4 text-center">
            <p className="text-xs text-gray-400 dark:text-gray-600">
              <a
                href="https://github.com/jwest33"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-600 dark:hover:text-gray-400 transition-colors inline-flex items-baseline"
              >
                <img
                  src="/mochi-synthwave-256.jpg"
                  alt="@"
                  className="inline-block h-[1em] w-[1em] object-cover rounded-sm align-baseline"
                />
                jwest33
              </a>
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
}
