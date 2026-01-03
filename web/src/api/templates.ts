import { apiClient, handleApiError } from './client';
import type { ResumeContent, RequirementsContent, TemplateValidation, ATSScoreResult, ResumeUploadResponse, ParsedResume } from '../types/template';

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

  async uploadResume(file: File): Promise<ResumeUploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await apiClient.post('/templates/resume/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getATSScore(): Promise<ATSScoreResult> {
    try {
      const response = await apiClient.post('/templates/resume/ats-score');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getCachedATSScore(): Promise<ATSScoreResult | null> {
    try {
      const response = await apiClient.get('/templates/resume/ats-score');
      return response.data;
    } catch (error) {
      // Return null if no cached score (404) or other error
      return null;
    }
  },

  async parseResume(): Promise<ParsedResume> {
    try {
      const response = await apiClient.post('/templates/resume/parse');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
