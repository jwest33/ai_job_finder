import { apiClient, handleApiError } from './client';
import type { HealthStatus, Profile } from '../types/api';

export const systemApi = {
  async getHealth(): Promise<HealthStatus> {
    try {
      const response = await apiClient.get('/system/health');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getProfiles(): Promise<Profile[]> {
    try {
      const response = await apiClient.get('/system/profiles');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async switchProfile(profileName: string): Promise<void> {
    try {
      await apiClient.post(`/system/profiles/${profileName}/activate`);
    } catch (error) {
      handleApiError(error);
    }
  },
};
