import { apiClient, handleApiError } from './client';
import type { Job, ApplicationStatus, PaginatedResponse } from '../types/job';

export interface ApplicationStats {
  total: number;
  by_status: Record<ApplicationStatus, number>;
  recent_applications: number;
  response_rate: number;
}

export const applicationsApi = {
  async getApplications(params: {
    status?: ApplicationStatus;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  } = {}): Promise<PaginatedResponse<Job>> {
    try {
      const response = await apiClient.get('/applications/', { params });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async updateApplication(
    jobUrl: string,
    data: {
      status: ApplicationStatus;
      notes?: string;
      applied_at?: string;
      next_action?: string;
      next_action_date?: string;
    }
  ): Promise<void> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      await apiClient.put(`/applications/${encodedUrl}`, data);
    } catch (error) {
      handleApiError(error);
    }
  },

  async getStats(): Promise<ApplicationStats> {
    try {
      const response = await apiClient.get('/applications/stats');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
