import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useJobStore } from '../store/jobStore';
import { useToast } from '../store/uiStore';
import { JobCard } from '../components/jobs/JobCard';
import { JobFilters } from '../components/jobs/JobFilters';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { Button } from '../components/common/Button';
import { ApplicationStatus } from '../types/job';

export function JobsPage() {
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const {
    jobs,
    loading,
    error,
    pagination,
    setPage,
    setFilters,
    updateApplicationStatus,
    fetchJobs,
  } = useJobStore();

  // Apply URL params as filters on mount
  useEffect(() => {
    const minScore = searchParams.get('min_score');
    if (minScore) {
      setFilters({ min_score: Number(minScore) });
    }
  }, [searchParams, setFilters]);

  const handleStatusChange = async (jobUrl: string, status: ApplicationStatus) => {
    try {
      await updateApplicationStatus(jobUrl, status);
      // Refetch jobs to ensure UI is in sync with server
      await fetchJobs();
      toast.success(`Status updated to ${status.replace('_', ' ')}`);
    } catch {
      toast.error('Failed to update status');
    }
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchJobs();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Jobs</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          {pagination.total} jobs found
        </p>
      </div>

      {/* Filters */}
      <JobFilters />

      {/* Content */}
      {loading ? (
        <LoadingPage message="Loading jobs..." />
      ) : error ? (
        <div className="bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 p-4 rounded-lg">
          {error}
        </div>
      ) : jobs.length === 0 ? (
        <div className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 p-8 rounded-lg text-center">
          <p className="text-lg font-medium">No jobs found</p>
          <p className="mt-1">Try adjusting your filters or run a new search</p>
        </div>
      ) : (
        <>
          {/* Job List */}
          <div className="space-y-4">
            {jobs.map((job) => (
              <JobCard
                key={job.job_url}
                job={job}
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>

          {/* Pagination */}
          {pagination.totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Showing {(pagination.page - 1) * pagination.pageSize + 1} to{' '}
                {Math.min(pagination.page * pagination.pageSize, pagination.total)} of{' '}
                {pagination.total} jobs
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePageChange(pagination.page - 1)}
                  disabled={pagination.page <= 1}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </Button>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Page {pagination.page} of {pagination.totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePageChange(pagination.page + 1)}
                  disabled={pagination.page >= pagination.totalPages}
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
