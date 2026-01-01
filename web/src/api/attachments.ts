import { apiClient, handleApiError } from './client';
import type { JobAttachment, AttachmentType } from '../types/job';

export interface AttachmentListResponse {
  items: JobAttachment[];
  total: number;
}

export interface AttachmentUploadResponse {
  success: boolean;
  attachment: JobAttachment;
  message: string;
}

export const attachmentsApi = {
  async getAttachments(jobUrl: string): Promise<AttachmentListResponse> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.get(`/attachments/${encodedUrl}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async uploadAttachment(
    jobUrl: string,
    file: File,
    attachmentType: AttachmentType,
    notes?: string
  ): Promise<AttachmentUploadResponse> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const formData = new FormData();
      formData.append('file', file);
      formData.append('attachment_type', attachmentType);
      if (notes) {
        formData.append('notes', notes);
      }

      const response = await apiClient.post(`/attachments/${encodedUrl}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  async downloadAttachment(jobUrl: string, attachmentId: string, filename: string): Promise<void> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      const response = await apiClient.get(
        `/attachments/${encodedUrl}/${attachmentId}/download`,
        { responseType: 'blob' }
      );

      // Create download link
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      handleApiError(error);
    }
  },

  async deleteAttachment(jobUrl: string, attachmentId: string): Promise<void> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      await apiClient.delete(`/attachments/${encodedUrl}/${attachmentId}`);
    } catch (error) {
      handleApiError(error);
    }
  },

  async updateAttachmentNotes(
    jobUrl: string,
    attachmentId: string,
    notes: string
  ): Promise<void> {
    try {
      const encodedUrl = encodeURIComponent(jobUrl);
      await apiClient.put(`/attachments/${encodedUrl}/${attachmentId}`, { notes });
    } catch (error) {
      handleApiError(error);
    }
  },
};
