/**
 * AI Provider Settings Types
 */

export interface AISettings {
  provider_type: 'openai_compatible';
  base_url: string;
  api_key: string;
  model: string;
  vision_model?: string | null;
  vision_enabled?: boolean | null;
  temperature: number;
  max_tokens: number;
  timeout: number;
  max_concurrent: number;
  has_custom_settings: boolean;
}

export interface AISettingsUpdate {
  provider_type?: string;
  base_url: string;
  api_key?: string | null;
  model: string;
  vision_model?: string | null;
  vision_enabled?: boolean | null;
  temperature?: number;
  max_tokens?: number;
  timeout?: number;
  max_concurrent?: number;
}

export interface ConnectionTestRequest {
  base_url: string;
  api_key?: string | null;
  model?: string;
  vision_enabled?: boolean | null;
}

export interface ConnectionTestResponse {
  success: boolean;
  capabilities: {
    text: boolean;
    vision: boolean;
  };
  models: string[];
  error?: string | null;
  model_info?: Record<string, unknown> | null;
}

export interface AIProviderPreset {
  id: string;
  name: string;
  base_url: string;
  model: string;
  description: string;
}

export interface AIStatus {
  connected: boolean;
  provider_type?: string;
  base_url?: string;
  has_vision?: boolean;
  capabilities?: {
    text: boolean;
    vision: boolean;
  };
  models?: string[];
  error?: string;
}

/**
 * Match Quality Threshold Settings
 */

export interface ThresholdSettings {
  excellent: number;
  good: number;
  fair: number;
  has_custom_settings: boolean;
}

export interface ThresholdSettingsUpdate {
  excellent: number;
  good: number;
  fair: number;
}
