import { create } from 'zustand';
import type { Job, JobFilters, ApplicationStatus } from '../types/job';
import { jobsApi } from '../api/jobs';
import { applicationsApi } from '../api/applications';

interface JobState {
  jobs: Job[];
  selectedJob: Job | null;
  loading: boolean;
  error: string | null;
  filters: JobFilters;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };

  // Actions
  fetchJobs: () => Promise<void>;
  setFilters: (filters: Partial<JobFilters>) => void;
  resetFilters: () => void;
  setPage: (page: number) => void;
  selectJob: (job: Job | null) => void;
  updateApplicationStatus: (jobUrl: string, status: ApplicationStatus, notes?: string) => Promise<void>;
}

const defaultFilters: JobFilters = {
  source: null,
  min_score: null,
  max_score: null,
  remote: null,
  location: null,
  company: null,
  status: null,
  search: null,
  sort_by: 'date_posted',
  sort_order: 'desc',
};

export const useJobStore = create<JobState>((set, get) => ({
  jobs: [],
  selectedJob: null,
  loading: false,
  error: null,
  filters: { ...defaultFilters },
  pagination: {
    page: 1,
    pageSize: 25,
    total: 0,
    totalPages: 0,
  },

  fetchJobs: async () => {
    const { filters, pagination } = get();
    set({ loading: true, error: null });

    try {
      const response = await jobsApi.getJobs({
        ...filters,
        page: pagination.page,
        page_size: pagination.pageSize,
      });

      set({
        jobs: response.items,
        pagination: {
          ...pagination,
          total: response.total,
          totalPages: response.total_pages,
        },
        loading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch jobs',
        loading: false,
      });
    }
  },

  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      pagination: { ...state.pagination, page: 1 },
    }));
  },

  resetFilters: () => {
    set({
      filters: { ...defaultFilters },
      pagination: { page: 1, pageSize: 25, total: 0, totalPages: 0 },
    });
  },

  setPage: (page) => {
    set((state) => ({
      pagination: { ...state.pagination, page },
    }));
  },

  selectJob: (job) => {
    set({ selectedJob: job });
  },

  updateApplicationStatus: async (jobUrl, status, notes) => {
    try {
      await applicationsApi.updateApplication(jobUrl, { status, notes });

      // Update local state
      set((state) => ({
        jobs: state.jobs.map((job) =>
          job.job_url === jobUrl
            ? { ...job, application_status: status, application_notes: notes }
            : job
        ),
        selectedJob:
          state.selectedJob?.job_url === jobUrl
            ? { ...state.selectedJob, application_status: status, application_notes: notes }
            : state.selectedJob,
      }));
    } catch (error) {
      throw error;
    }
  },
}));
