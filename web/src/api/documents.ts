import { apiClient, handleApiError } from './client';
import type {
  ResumeRewriteRequest,
  ResumeRewriteResponse,
  CoverLetterRequest,
  CoverLetterResponse,
  SavedCoverLetter,
  SectionRegenerateRequest,
  SectionRegenerateResponse,
} from '../types/document';

// Extend timeout for AI generation operations
const AI_TIMEOUT = 120000; // 2 minutes

export interface TailoredDocument {
  found: boolean;
  document_type?: string;
  plain_text?: string;
  structured_data?: Record<string, unknown>;
  verification_data?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface CoverLetterTemplate {
  found: boolean;
  content?: string;
}

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

  async regenerateSection(request: SectionRegenerateRequest): Promise<SectionRegenerateResponse> {
    try {
      const response = await apiClient.post('/documents/resume/regenerate-section', request, {
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

  // Tailored documents
  async getTailoredDocument(documentType: 'resume' | 'cover_letter', jobUrl: string): Promise<TailoredDocument> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.get(`/documents/tailored/${documentType}/${encodedUrl}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async deleteTailoredDocument(documentType: 'resume' | 'cover_letter', jobUrl: string): Promise<{ success: boolean }> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.delete(`/documents/tailored/${documentType}/${encodedUrl}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  // Cover letter template
  async getCoverLetterTemplate(): Promise<CoverLetterTemplate> {
    try {
      const response = await apiClient.get('/documents/cover-letter/template');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async uploadCoverLetterTemplate(content: string): Promise<{ success: boolean; message: string }> {
    try {
      const response = await apiClient.put('/documents/cover-letter/template', { content });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
