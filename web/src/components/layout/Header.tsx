import { Menu, Bell, User } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';
import { ProfileSelector } from './ProfileSelector';

export function Header() {
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
      <div className="flex items-center justify-between h-16 px-4">
        {/* Left */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <span className="font-semibold text-gray-900">Job Finder</span>
          </div>
        </div>

        {/* Right */}
        <div className="flex items-center gap-3">
          <ProfileSelector />
          <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors relative">
            <Bell className="w-5 h-5 text-gray-600" />
          </button>
          <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
            <User className="w-5 h-5 text-gray-600" />
          </button>
        </div>
      </div>
    </header>
  );
}
