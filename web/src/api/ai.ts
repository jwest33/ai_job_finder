import { apiClient, handleApiError } from './client';
import type {
  AISettings,
  AISettingsUpdate,
  ConnectionTestRequest,
  ConnectionTestResponse,
  AIProviderPreset,
  AIStatus,
  ThresholdSettings,
  ThresholdSettingsUpdate,
} from '../types/ai';

export const aiApi = {
  /**
   * Get current AI provider settings
   */
  async getSettings(): Promise<AISettings> {
    try {
      const response = await apiClient.get('/ai/settings');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Update AI provider settings
   */
  async updateSettings(settings: AISettingsUpdate): Promise<AISettings> {
    try {
      const response = await apiClient.put('/ai/settings', settings);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Reset settings to environment defaults
   */
  async resetSettings(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await apiClient.delete('/ai/settings');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Test connection to AI provider
   */
  async testConnection(request: ConnectionTestRequest): Promise<ConnectionTestResponse> {
    try {
      const response = await apiClient.post('/ai/test', request);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * List available models from current provider
   */
  async listModels(): Promise<string[]> {
    try {
      const response = await apiClient.get('/ai/models');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Get all provider presets
   */
  async getPresets(): Promise<AIProviderPreset[]> {
    try {
      const response = await apiClient.get('/ai/presets');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Apply a preset configuration
   */
  async applyPreset(presetId: string): Promise<AISettings> {
    try {
      const response = await apiClient.post(`/ai/presets/${presetId}/apply`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Get current AI provider status
   */
  async getStatus(): Promise<AIStatus> {
    try {
      const response = await apiClient.get('/ai/status');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  // ============================================================================
  // Match Quality Threshold Settings
  // ============================================================================

  /**
   * Get current match quality threshold settings
   */
  async getThresholds(): Promise<ThresholdSettings> {
    try {
      const response = await apiClient.get('/ai/thresholds');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Update match quality threshold settings
   */
  async updateThresholds(settings: ThresholdSettingsUpdate): Promise<ThresholdSettings> {
    try {
      const response = await apiClient.put('/ai/thresholds', settings);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Reset threshold settings to defaults
   */
  async resetThresholds(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await apiClient.delete('/ai/thresholds');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
