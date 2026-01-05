import { apiClient, handleApiError } from './client';
import type {
  ResumeRewriteRequest,
  ResumeRewriteResponse,
  CoverLetterRequest,
  CoverLetterResponse,
  SavedCoverLetter,
} from '../types/document';

// Extend timeout for AI generation operations
const AI_TIMEOUT = 120000; // 2 minutes

export const documentsApi = {
  async rewriteResume(request: ResumeRewriteRequest): Promise<ResumeRewriteResponse> {
    try {
      const response = await apiClient.post('/documents/resume/rewrite', request, {
        timeout: AI_TIMEOUT,
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async generateCoverLetter(request: CoverLetterRequest): Promise<CoverLetterResponse> {
    try {
      const response = await apiClient.post('/documents/cover-letter/generate', request, {
        timeout: AI_TIMEOUT,
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async saveCoverLetter(jobUrl: string, content: string): Promise<{ success: boolean; message: string }> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.post(`/documents/cover-letter/${encodedUrl}/save`, { content });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async getSavedCoverLetter(jobUrl: string): Promise<SavedCoverLetter> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.get(`/documents/cover-letter/${encodedUrl}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
