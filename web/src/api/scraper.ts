import { apiClient, handleApiError } from './client';
import type { TaskResponse } from '../types/api';

export interface SearchParams {
  jobs: string[];
  locations: string[];
  results_per_search?: number;
  scrapers?: string[];
}

export interface MatchParams {
  source?: string;
  min_score?: number;
  full_pipeline?: boolean;
  re_match_all?: boolean;
}

export const scraperApi = {
  async startSearch(params: SearchParams): Promise<{ task_id: string }> {
    try {
      const response = await apiClient.post('/scraper/search', params);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getSearchStatus(taskId: string): Promise<TaskResponse> {
    try {
      const response = await apiClient.get(`/scraper/search/${taskId}/status`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async startMatching(params: MatchParams): Promise<{ task_id: string }> {
    try {
      const response = await apiClient.post('/scraper/match', params);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getMatchStatus(taskId: string): Promise<TaskResponse> {
    try {
      const response = await apiClient.get(`/scraper/match/${taskId}/status`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getConfig(): Promise<{
    search_terms: string[];
    locations: string[];
    scrapers: string[];
    results_per_search: number;
  }> {
    try {
      const response = await apiClient.get('/scraper/config');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
