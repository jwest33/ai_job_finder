import { apiClient, handleApiError } from './client';
import type { Job, JobFilters, JobStats, PaginatedResponse, ApplicationStatus } from '../types/job';

export interface GetJobsParams extends Partial<JobFilters> {
  page?: number;
  page_size?: number;
}

export const jobsApi = {
  async getJobs(params: GetJobsParams = {}): Promise<PaginatedResponse<Job>> {
    try {
      const response = await apiClient.get('/jobs/', { params });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getJob(jobUrl: string): Promise<Job> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.get(`/jobs/${encodedUrl}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getStats(): Promise<JobStats> {
    try {
      const response = await apiClient.get('/jobs/stats');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getSources(): Promise<{ source: string; count: number }[]> {
    try {
      const response = await apiClient.get('/jobs/sources');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async updateApplicationStatus(
    jobUrl: string,
    status: ApplicationStatus,
    notes?: string
  ): Promise<void> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      await apiClient.put(`/applications/${encodedUrl}`, { status, notes });
    } catch (error) {
      handleApiError(error);
    }
  },
};
