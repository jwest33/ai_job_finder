import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X, SlidersHorizontal } from 'lucide-react';
import { useJobStore } from '../../store/jobStore';
import { jobsApi } from '../../api/jobs';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { APPLICATION_STATUS_LABELS, ApplicationStatus } from '../../types/job';

export function JobFilters() {
  const { filters, setFilters, resetFilters, fetchJobs } = useJobStore();

  const { data: sources } = useQuery({
    queryKey: ['job-sources'],
    queryFn: jobsApi.getSources,
  });

  // Fetch jobs when filters change
  useEffect(() => {
    fetchJobs();
  }, [filters, fetchJobs]);

  const sourceOptions = [
    { value: '', label: 'All Sources' },
    ...(sources?.map((s) => ({ value: s.source, label: `${s.source} (${s.count})` })) || []),
  ];

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    ...Object.entries(APPLICATION_STATUS_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  ];

  const sortOptions = [
    { value: 'date_posted', label: 'Date Posted' },
    { value: 'match_score', label: 'Match Score' },
    { value: 'first_seen', label: 'Date Added' },
    { value: 'company', label: 'Company' },
    { value: 'title', label: 'Title' },
  ];

  const hasActiveFilters =
    filters.source ||
    filters.min_score ||
    filters.remote !== null ||
    filters.status ||
    filters.search;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center gap-2 mb-4">
        <SlidersHorizontal className="w-5 h-5 text-gray-500 dark:text-gray-400" />
        <h3 className="font-medium text-gray-900 dark:text-white">Filters</h3>
        {hasActiveFilters && (
          <button
            onClick={resetFilters}
            className="ml-auto flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <X className="w-4 h-4" />
            Clear all
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Search */}
        <div className="lg:col-span-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search jobs..."
              value={filters.search || ''}
              onChange={(e) => setFilters({ search: e.target.value || null })}
              className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Source */}
        <Select
          value={filters.source || ''}
          onChange={(e) => setFilters({ source: e.target.value || null })}
          options={sourceOptions}
        />

        {/* Status */}
        <Select
          value={filters.status || ''}
          onChange={(e) => setFilters({ status: (e.target.value as ApplicationStatus) || null })}
          options={statusOptions}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        {/* Min Score */}
        <Input
          type="number"
          placeholder="Min Score"
          value={filters.min_score || ''}
          onChange={(e) => setFilters({ min_score: e.target.value ? Number(e.target.value) : null })}
          min={0}
          max={100}
        />

        {/* Remote */}
        <Select
          value={filters.remote === null ? '' : filters.remote ? 'true' : 'false'}
          onChange={(e) =>
            setFilters({
              remote: e.target.value === '' ? null : e.target.value === 'true',
            })
          }
          options={[
            { value: '', label: 'Remote & Onsite' },
            { value: 'true', label: 'Remote Only' },
            { value: 'false', label: 'Onsite Only' },
          ]}
        />

        {/* Sort */}
        <Select
          value={filters.sort_by}
          onChange={(e) =>
            setFilters({ sort_by: e.target.value as 'date_posted' | 'match_score' | 'first_seen' | 'company' | 'title' })
          }
          options={sortOptions}
        />

        {/* Sort Order */}
        <Select
          value={filters.sort_order}
          onChange={(e) => setFilters({ sort_order: e.target.value as 'asc' | 'desc' })}
          options={[
            { value: 'desc', label: 'Descending' },
            { value: 'asc', label: 'Ascending' },
          ]}
        />
      </div>
    </div>
  );
}
