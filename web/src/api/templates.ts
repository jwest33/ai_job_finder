import { apiClient, handleApiError } from './client';
import type { ResumeContent, RequirementsContent, TemplateValidation } from '../types/template';

export const templatesApi = {
  async getResume(): Promise<ResumeContent> {
    try {
      const response = await apiClient.get('/templates/resume');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async updateResume(content: string): Promise<void> {
    try {
      await apiClient.put('/templates/resume', { content });
    } catch (error) {
      handleApiError(error);
    }
  },

  async getRequirements(): Promise<RequirementsContent> {
    try {
      const response = await apiClient.get('/templates/requirements');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async updateRequirements(content: string): Promise<void> {
    try {
      await apiClient.put('/templates/requirements', { content });
    } catch (error) {
      handleApiError(error);
    }
  },

  async validate(): Promise<TemplateValidation> {
    try {
      const response = await apiClient.post('/templates/validate');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
