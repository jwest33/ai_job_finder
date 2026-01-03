import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { applicationsApi } from '../api/applications';
import { JobCard } from '../components/jobs/JobCard';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { Card, CardTitle } from '../components/common/Card';
import { useToast } from '../store/uiStore';
import { useJobStore } from '../store/jobStore';
import {
  ApplicationStatus,
  APPLICATION_STATUS_LABELS,
  APPLICATION_STATUS_COLORS,
} from '../types/job';
import clsx from 'clsx';

const STATUS_TABS: ApplicationStatus[] = [
  'applied',
  'phone_screen',
  'interviewing',
  'final_round',
  'offer',
  'rejected',
];

export function ApplicationsPage() {
  const [activeStatus, setActiveStatus] = useState<ApplicationStatus | null>(null);
  const toast = useToast();
  const { updateApplicationStatus } = useJobStore();

  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['application-stats'],
    queryFn: applicationsApi.getStats,
  });

  const { data: applications, isLoading: loadingApps } = useQuery({
    queryKey: ['applications', activeStatus],
    queryFn: () =>
      applicationsApi.getApplications({
        status: activeStatus || undefined,
        sort_by: 'updated_at',
        sort_order: 'desc',
      }),
  });

  const handleStatusChange = async (jobUrl: string, status: ApplicationStatus) => {
    try {
      await updateApplicationStatus(jobUrl, status);
      toast.success(`Status updated to ${status.replace('_', ' ')}`);
    } catch {
      toast.error('Failed to update status');
    }
  };

  if (loadingStats) {
    return <LoadingPage message="Loading applications..." />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Applications</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Track your job application progress</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {STATUS_TABS.map((status) => (
          <button
            key={status}
            onClick={() => setActiveStatus(activeStatus === status ? null : status)}
            className={clsx(
              'p-4 rounded-lg border transition-colors text-center',
              activeStatus === status
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
            )}
          >
            <div
              className={clsx(
                'text-2xl font-bold',
                activeStatus === status ? 'text-blue-600 dark:text-blue-400' : 'text-gray-900 dark:text-white'
              )}
            >
              {stats?.by_status?.[status] || 0}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {APPLICATION_STATUS_LABELS[status]}
            </div>
          </button>
        ))}
      </div>

      {/* Application Pipeline Visualization */}
      <Card>
        <CardTitle>Application Pipeline</CardTitle>
        <div className="mt-4 flex items-center">
          {STATUS_TABS.slice(0, 5).map((status, index) => (
            <div key={status} className="flex-1 flex items-center">
              <div className="flex-1">
                <div
                  className={clsx(
                    'h-2 rounded-l-full',
                    index === 0 && 'rounded-l-full',
                    APPLICATION_STATUS_COLORS[status].replace('text-', 'bg-').split(' ')[0]
                  )}
                  style={{
                    opacity: stats?.by_status?.[status] ? 1 : 0.3,
                  }}
                />
                <div className="text-center mt-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {APPLICATION_STATUS_LABELS[status]}
                  </span>
                </div>
              </div>
              {index < 4 && (
                <div className="w-4 h-2 bg-gray-200 dark:bg-gray-700" />
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Filter Info */}
      {activeStatus && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">Filtering by:</span>
          <span
            className={clsx(
              'px-2 py-1 rounded-full text-xs font-medium',
              APPLICATION_STATUS_COLORS[activeStatus]
            )}
          >
            {APPLICATION_STATUS_LABELS[activeStatus]}
          </span>
          <button
            onClick={() => setActiveStatus(null)}
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            Clear filter
          </button>
        </div>
      )}

      {/* Applications List */}
      {loadingApps ? (
        <LoadingPage message="Loading applications..." />
      ) : applications?.items.length === 0 ? (
        <div className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 p-8 rounded-lg text-center">
          <p className="text-lg font-medium">No applications found</p>
          <p className="mt-1">
            {activeStatus
              ? `No jobs with status "${APPLICATION_STATUS_LABELS[activeStatus]}"`
              : 'Start applying to jobs to track them here'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {applications?.items.map((job) => (
            <JobCard
              key={job.job_url}
              job={job}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      )}
    </div>
  );
}
