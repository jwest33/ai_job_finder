import { useState, useEffect, useRef } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { systemApi } from '../../api/system';
import { useToast } from '../../store/uiStore';
import { useJobStore } from '../../store/jobStore';
import clsx from 'clsx';

export function ProfileSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const queryClient = useQueryClient();
  const { fetchJobs, resetFilters } = useJobStore();

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: systemApi.getProfiles,
  });

  const switchMutation = useMutation({
    mutationFn: systemApi.switchProfile,
    onSuccess: () => {
      // Invalidate all profile-dependent queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job-stats'] });
      queryClient.invalidateQueries({ queryKey: ['job-sources'] });
      queryClient.invalidateQueries({ queryKey: ['resume'] });
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
      queryClient.invalidateQueries({ queryKey: ['template-validation'] });
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      queryClient.invalidateQueries({ queryKey: ['application-stats'] });

      // Reset filters and refetch jobs from Zustand store
      resetFilters();
      fetchJobs();

      toast.success('Profile switched successfully');
      setIsOpen(false);
    },
    onError: () => {
      toast.error('Failed to switch profile');
    },
  });

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeProfile = profiles?.find((p) => p.is_active);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
        disabled={isLoading}
      >
        <span className="text-sm font-medium text-gray-700">
          {activeProfile?.name || 'Loading...'}
        </span>
        <ChevronDown className={clsx('w-4 h-4 text-gray-500 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && profiles && (
        <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
          {profiles.map((profile) => (
            <button
              key={profile.name}
              onClick={() => switchMutation.mutate(profile.name)}
              className="w-full flex items-center justify-between px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              <span>{profile.name}</span>
              {profile.is_active && <Check className="w-4 h-4 text-blue-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
