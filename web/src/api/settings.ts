/**
 * Settings API client for prompt configuration and tracing.
 */

import { apiClient, handleApiError } from './client';

// =============================================================================
// Types
// =============================================================================

export interface LLMParameters {
  temperature: number;
  max_tokens: number;
  max_retries: number;
}

// Partial update type for LLM parameters
export interface LLMParametersUpdate {
  temperature?: number;
  max_tokens?: number;
  max_retries?: number;
}

// Update types with partial parameters
export interface ResumeRewriterUpdate {
  system_prompt?: string;
  parameters?: LLMParametersUpdate;
  max_keywords?: number;
  summary_instructions?: string;
  experience_instructions?: string;
  skills_instructions?: string;
}

export interface CoverLetterUpdate {
  system_prompt?: string;
  parameters?: LLMParametersUpdate;
  default_tone?: string;
  default_max_words?: number;
  opening_instructions?: string;
  body_instructions?: string;
  closing_instructions?: string;
}

export interface VerificationUpdate {
  enabled?: boolean;
  llm_verification_prompt?: string;
  parameters?: LLMParametersUpdate;
}

export interface ResumeRewriterConfig {
  system_prompt: string;
  parameters: LLMParameters;
  max_keywords: number;
  summary_instructions: string;
  experience_instructions: string;
  skills_instructions: string;
}

export interface CoverLetterConfig {
  system_prompt: string;
  parameters: LLMParameters;
  default_tone: string;
  default_max_words: number;
  opening_instructions: string;
  body_instructions: string;
  closing_instructions: string;
}

export interface VerificationConfig {
  enabled: boolean;
  llm_verification_prompt: string;
  parameters: LLMParameters;
}

export interface PromptConfig {
  version: string;
  updated_at: string | null;
  resume_rewriter: ResumeRewriterConfig;
  cover_letter: CoverLetterConfig;
  verification: VerificationConfig;
}

export interface LLMTrace {
  id: string;
  timestamp: string;
  operation: string;
  model: string;
  temperature: number;
  system_prompt: string;
  user_prompt: string;
  response: string | null;
  parsed_response: Record<string, unknown> | null;
  validation_passed: boolean;
  validation_errors: string[];
  retry_count: number;
  duration_ms: number | null;
  job_title: string | null;
  job_company: string | null;
  metadata: Record<string, unknown>;
}

export interface TraceStats {
  total_traces: number;
  failed_traces: number;
  success_rate: number;
  operations: Record<string, number>;
  avg_retries: number;
  active_traces: number;
}

export interface TracesResponse {
  traces: LLMTrace[];
  stats: TraceStats;
}

// =============================================================================
// Prompt Configuration API
// =============================================================================

export const settingsApi = {
  /**
   * Get the current prompt configuration.
   */
  async getPromptConfig(): Promise<PromptConfig> {
    try {
      const response = await apiClient.get('/settings/prompts');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Update resume rewriter configuration.
   */
  async updateResumeRewriter(updates: ResumeRewriterUpdate): Promise<{ success: boolean; config: ResumeRewriterConfig }> {
    try {
      const response = await apiClient.put('/settings/prompts/resume-rewriter', updates);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Update cover letter configuration.
   */
  async updateCoverLetter(updates: CoverLetterUpdate): Promise<{ success: boolean; config: CoverLetterConfig }> {
    try {
      const response = await apiClient.put('/settings/prompts/cover-letter', updates);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Update verification configuration.
   */
  async updateVerification(updates: VerificationUpdate): Promise<{ success: boolean; config: VerificationConfig }> {
    try {
      const response = await apiClient.put('/settings/prompts/verification', updates);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Reset prompt configuration to defaults.
   */
  async resetToDefaults(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await apiClient.post('/settings/prompts/reset');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Get default prompts for reference.
   */
  async getDefaults(): Promise<Omit<PromptConfig, 'version' | 'updated_at'>> {
    try {
      const response = await apiClient.get('/settings/prompts/defaults');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  // ===========================================================================
  // Tracing API
  // ===========================================================================

  /**
   * Get recent LLM traces.
   */
  async getTraces(options?: {
    limit?: number;
    operation?: string;
    failedOnly?: boolean;
  }): Promise<TracesResponse> {
    try {
      const params: Record<string, string> = {};
      if (options?.limit) params.limit = options.limit.toString();
      if (options?.operation) params.operation = options.operation;
      if (options?.failedOnly) params.failed_only = 'true';

      const response = await apiClient.get('/settings/traces', { params });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Get a specific trace by ID.
   */
  async getTrace(traceId: string): Promise<LLMTrace> {
    try {
      const response = await apiClient.get(`/settings/traces/${traceId}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Clear all stored traces.
   */
  async clearTraces(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await apiClient.delete('/settings/traces');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Get tracing statistics.
   */
  async getTraceStats(): Promise<TraceStats> {
    try {
      const response = await apiClient.get('/settings/traces/stats');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },

  /**
   * Enable or disable tracing.
   */
  async setTracingEnabled(enabled: boolean): Promise<{ success: boolean; enabled: boolean }> {
    try {
      const response = await apiClient.put('/settings/traces/enabled', null, {
        params: { enabled },
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};
