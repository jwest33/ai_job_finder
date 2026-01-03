import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Save,
  Settings,
  Cpu,
  Eye,
  EyeOff,
  Zap,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Server,
  Target,
} from 'lucide-react';
import { aiApi } from '../api/ai';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { useToast } from '../store/uiStore';
import type { AISettingsUpdate, AIProviderPreset, ConnectionTestResponse, ThresholdSettingsUpdate } from '../types/ai';
import clsx from 'clsx';

export function SettingsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();

  // Form state
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [visionModel, setVisionModel] = useState('');
  const [visionEnabled, setVisionEnabled] = useState<boolean | null>(null);
  const [temperature, setTemperature] = useState(0.3);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [timeout, setTimeout] = useState(300);
  const [maxConcurrent, setMaxConcurrent] = useState(4);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Connection test state
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Threshold settings state
  const [excellentThreshold, setExcellentThreshold] = useState(80);
  const [goodThreshold, setGoodThreshold] = useState(60);
  const [fairThreshold, setFairThreshold] = useState(40);
  const [hasUnsavedThresholds, setHasUnsavedThresholds] = useState(false);

  // Load current settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: aiApi.getSettings,
  });

  // Load threshold settings
  const { data: thresholds, isLoading: isLoadingThresholds } = useQuery({
    queryKey: ['threshold-settings'],
    queryFn: aiApi.getThresholds,
  });

  // Load presets
  const { data: presets } = useQuery({
    queryKey: ['ai-presets'],
    queryFn: aiApi.getPresets,
  });

  // Sync form state when settings load
  useEffect(() => {
    if (settings) {
      setBaseUrl(settings.base_url);
      setApiKey(''); // Don't show masked key in input
      setModel(settings.model);
      setVisionModel(settings.vision_model || '');
      setVisionEnabled(settings.vision_enabled);
      setTemperature(settings.temperature);
      setMaxTokens(settings.max_tokens);
      setTimeout(settings.timeout);
      setMaxConcurrent(settings.max_concurrent);
      setHasUnsavedChanges(false);
    }
  }, [settings]);

  // Sync threshold state when thresholds load
  useEffect(() => {
    if (thresholds) {
      setExcellentThreshold(thresholds.excellent);
      setGoodThreshold(thresholds.good);
      setFairThreshold(thresholds.fair);
      setHasUnsavedThresholds(false);
    }
  }, [thresholds]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (update: AISettingsUpdate) => aiApi.updateSettings(update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] });
      queryClient.invalidateQueries({ queryKey: ['health'] });
      toast.success('Settings saved successfully');
      setHasUnsavedChanges(false);
    },
    onError: () => {
      toast.error('Failed to save settings');
    },
  });

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: () => aiApi.resetSettings(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] });
      queryClient.invalidateQueries({ queryKey: ['health'] });
      toast.success('Settings reset to defaults');
      setHasUnsavedChanges(false);
    },
    onError: () => {
      toast.error('Failed to reset settings');
    },
  });

  // Apply preset mutation
  const applyPresetMutation = useMutation({
    mutationFn: (presetId: string) => aiApi.applyPreset(presetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] });
      toast.success('Preset applied');
    },
    onError: () => {
      toast.error('Failed to apply preset');
    },
  });

  // Threshold save mutation
  const saveThresholdsMutation = useMutation({
    mutationFn: (update: ThresholdSettingsUpdate) => aiApi.updateThresholds(update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threshold-settings'] });
      toast.success('Thresholds saved successfully');
      setHasUnsavedThresholds(false);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to save thresholds');
    },
  });

  // Threshold reset mutation
  const resetThresholdsMutation = useMutation({
    mutationFn: () => aiApi.resetThresholds(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threshold-settings'] });
      toast.success('Thresholds reset to defaults');
      setHasUnsavedThresholds(false);
    },
    onError: () => {
      toast.error('Failed to reset thresholds');
    },
  });

  const handleSave = () => {
    saveMutation.mutate({
      base_url: baseUrl,
      api_key: apiKey || null,
      model,
      vision_model: visionModel || null,
      vision_enabled: visionEnabled,
      temperature,
      max_tokens: maxTokens,
      timeout,
      max_concurrent: maxConcurrent,
    });
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await aiApi.testConnection({
        base_url: baseUrl,
        api_key: apiKey || undefined,
        model,
        vision_enabled: visionEnabled,
      });
      setTestResult(result);
      if (result.success) {
        toast.success('Connection successful');
      } else {
        toast.error(result.error || 'Connection failed');
      }
    } catch {
      toast.error('Connection test failed');
    } finally {
      setIsTesting(false);
    }
  };

  const handlePresetClick = (preset: AIProviderPreset) => {
    setBaseUrl(preset.base_url);
    setModel(preset.model);
    setHasUnsavedChanges(true);
  };

  const markChanged = () => {
    setHasUnsavedChanges(true);
  };

  const handleSaveThresholds = () => {
    // Validate order before saving
    if (!(fairThreshold < goodThreshold && goodThreshold < excellentThreshold)) {
      toast.error('Thresholds must be in order: Fair < Good < Excellent');
      return;
    }
    saveThresholdsMutation.mutate({
      excellent: excellentThreshold,
      good: goodThreshold,
      fair: fairThreshold,
    });
  };

  const markThresholdsChanged = () => {
    setHasUnsavedThresholds(true);
  };

  // Helper to get threshold validation error
  const getThresholdError = (): string | null => {
    if (fairThreshold >= goodThreshold) return 'Fair must be less than Good';
    if (goodThreshold >= excellentThreshold) return 'Good must be less than Excellent';
    return null;
  };

  const thresholdError = getThresholdError();

  if (isLoading || isLoadingThresholds) {
    return <LoadingPage message="Loading settings..." />;
  }

  const isSaving = saveMutation.isPending;
  const isSavingThresholds = saveThresholdsMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Settings</h1>
          <p className="text-gray-500 mt-1">Configure your AI provider for job matching and analysis</p>
        </div>
        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <span className="text-sm text-yellow-600">Unsaved changes</span>
          )}
          <Button
            variant="secondary"
            onClick={handleTestConnection}
            disabled={isTesting || !baseUrl}
            loading={isTesting}
          >
            <Zap className="w-4 h-4 mr-2" />
            Test Connection
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasUnsavedChanges || isSaving}
            loading={isSaving}
          >
            <Save className="w-4 h-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Connection Status */}
      {testResult && (
        <div
          className={clsx(
            'rounded-lg p-4 border',
            testResult.success
              ? 'bg-green-50 border-green-200'
              : 'bg-red-50 border-red-200'
          )}
        >
          <div className="flex items-center gap-2">
            {testResult.success ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600" />
            )}
            <span
              className={clsx(
                'font-medium',
                testResult.success ? 'text-green-700' : 'text-red-700'
              )}
            >
              {testResult.success ? 'Connection Successful' : 'Connection Failed'}
            </span>
          </div>
          {testResult.success && (
            <div className="mt-2 text-sm text-green-600 space-y-1">
              <p>
                Text Generation: {testResult.capabilities.text ? 'Available' : 'Not available'}
              </p>
              <p>
                Vision: {testResult.capabilities.vision ? 'Available' : 'Not available'}
              </p>
              {testResult.models.length > 0 && (
                <p>Available models: {testResult.models.slice(0, 5).join(', ')}</p>
              )}
            </div>
          )}
          {testResult.error && (
            <p className="mt-2 text-sm text-red-600">{testResult.error}</p>
          )}
        </div>
      )}

      {/* Presets */}
      {presets && presets.length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold">Quick Setup</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {presets.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handlePresetClick(preset)}
                className="p-3 border rounded-lg text-left hover:bg-gray-50 transition-colors"
              >
                <div className="font-medium text-sm">{preset.name}</div>
                <div className="text-xs text-gray-500 mt-1 truncate">
                  {preset.model}
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Main Settings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection Settings */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold">Provider Settings</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Endpoint
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => {
                  setBaseUrl(e.target.value);
                  markChanged();
                }}
                placeholder="http://localhost:8080/v1"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                OpenAI-compatible endpoint (e.g., llama-server, Ollama, OpenAI)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key (optional)
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    markChanged();
                  }}
                  placeholder={settings?.api_key ? '(unchanged)' : 'sk-...'}
                  className="w-full px-3 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showApiKey ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Required for cloud providers (OpenAI, Anthropic)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => {
                  setModel(e.target.value);
                  markChanged();
                }}
                placeholder="default"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Model name/ID (e.g., gpt-4o, llama3.2, default)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Vision Model (optional)
              </label>
              <input
                type="text"
                value={visionModel}
                onChange={(e) => {
                  setVisionModel(e.target.value);
                  markChanged();
                }}
                placeholder="(same as model)"
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">Vision</label>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setVisionEnabled(null);
                    markChanged();
                  }}
                  className={clsx(
                    'px-3 py-1 text-sm rounded-lg border',
                    visionEnabled === null
                      ? 'bg-blue-100 border-blue-300 text-blue-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  )}
                >
                  Auto
                </button>
                <button
                  onClick={() => {
                    setVisionEnabled(true);
                    markChanged();
                  }}
                  className={clsx(
                    'px-3 py-1 text-sm rounded-lg border',
                    visionEnabled === true
                      ? 'bg-green-100 border-green-300 text-green-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  )}
                >
                  Enabled
                </button>
                <button
                  onClick={() => {
                    setVisionEnabled(false);
                    markChanged();
                  }}
                  className={clsx(
                    'px-3 py-1 text-sm rounded-lg border',
                    visionEnabled === false
                      ? 'bg-red-100 border-red-300 text-red-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  )}
                >
                  Disabled
                </button>
              </div>
            </div>
          </div>
        </Card>

        {/* Generation Settings */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Settings className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold">Generation Settings</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Temperature: {temperature.toFixed(2)}
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => {
                  setTemperature(parseFloat(e.target.value));
                  markChanged();
                }}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>Precise (0)</span>
                <span>Creative (2)</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Tokens
              </label>
              <input
                type="number"
                min="1"
                max="32768"
                value={maxTokens}
                onChange={(e) => {
                  setMaxTokens(parseInt(e.target.value) || 2048);
                  markChanged();
                }}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Maximum tokens to generate per response
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Timeout (seconds)
              </label>
              <input
                type="number"
                min="10"
                max="3600"
                value={timeout}
                onChange={(e) => {
                  setTimeout(parseInt(e.target.value) || 300);
                  markChanged();
                }}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Concurrent Requests
              </label>
              <input
                type="number"
                min="1"
                max="32"
                value={maxConcurrent}
                onChange={(e) => {
                  setMaxConcurrent(parseInt(e.target.value) || 4);
                  markChanged();
                }}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                Number of parallel requests during batch processing
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Match Quality Thresholds */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold">Match Quality Thresholds</h2>
          </div>
          <div className="flex items-center gap-3">
            {hasUnsavedThresholds && (
              <span className="text-sm text-yellow-600">Unsaved changes</span>
            )}
            <Button
              size="sm"
              onClick={handleSaveThresholds}
              disabled={!hasUnsavedThresholds || isSavingThresholds || !!thresholdError}
              loading={isSavingThresholds}
            >
              <Save className="w-4 h-4 mr-2" />
              Save Thresholds
            </Button>
          </div>
        </div>

        <p className="text-sm text-gray-500 mb-4">
          Configure score thresholds that determine job match quality ratings.
          Jobs are rated based on where their score falls relative to these thresholds.
        </p>

        {thresholdError && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            {thresholdError}
          </div>
        )}

        <div className="space-y-6">
          {/* Excellent threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                Excellent (Green)
              </label>
              <span className="text-sm font-mono bg-green-100 text-green-700 px-2 py-0.5 rounded">
                ≥ {excellentThreshold}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              value={excellentThreshold}
              onChange={(e) => {
                setExcellentThreshold(parseInt(e.target.value));
                markThresholdsChanged();
              }}
              className="w-full accent-green-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Scores at or above this value are rated "Excellent"
            </p>
          </div>

          {/* Good threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                Good (Yellow)
              </label>
              <span className="text-sm font-mono bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                ≥ {goodThreshold}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="99"
              value={goodThreshold}
              onChange={(e) => {
                setGoodThreshold(parseInt(e.target.value));
                markThresholdsChanged();
              }}
              className="w-full accent-yellow-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Scores at or above this value (but below Excellent) are rated "Good"
            </p>
          </div>

          {/* Fair threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                Fair (Orange)
              </label>
              <span className="text-sm font-mono bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                ≥ {fairThreshold}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="98"
              value={fairThreshold}
              onChange={(e) => {
                setFairThreshold(parseInt(e.target.value));
                markThresholdsChanged();
              }}
              className="w-full accent-orange-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Scores at or above this value (but below Good) are rated "Fair"
            </p>
          </div>

          {/* Preview */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Preview</h3>
            <div className="flex gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-green-500" />
                <span>Excellent: {excellentThreshold}-100</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-yellow-500" />
                <span>Good: {goodThreshold}-{excellentThreshold - 1}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-orange-500" />
                <span>Fair: {fairThreshold}-{goodThreshold - 1}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500" />
                <span>Low: 0-{fairThreshold - 1}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Reset Thresholds */}
        <div className="flex items-center justify-between mt-6 pt-4 border-t">
          <div>
            <h3 className="font-medium text-gray-900">Reset Thresholds</h3>
            <p className="text-sm text-gray-500">
              Restore default thresholds (80/60/40)
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => resetThresholdsMutation.mutate()}
            disabled={!thresholds?.has_custom_settings}
            loading={resetThresholdsMutation.isPending}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Reset
          </Button>
        </div>
      </Card>

      {/* Actions */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900">Reset AI Settings</h3>
            <p className="text-sm text-gray-500">
              Remove custom settings and revert to environment defaults
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => resetMutation.mutate()}
            disabled={!settings?.has_custom_settings}
            loading={resetMutation.isPending}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Reset to Defaults
          </Button>
        </div>
      </Card>

      {/* Help Text */}
      <div className="text-sm text-gray-500 space-y-2">
        <p>
          This app supports any OpenAI-compatible API. For local inference, use:
        </p>
        <ul className="list-disc list-inside ml-2 space-y-1">
          <li>
            <strong>llama-server:</strong> http://localhost:8080/v1 (requires -oai flag)
          </li>
          <li>
            <strong>Ollama:</strong> http://localhost:11434/v1
          </li>
          <li>
            <strong>LM Studio:</strong> http://localhost:1234/v1
          </li>
        </ul>
        <p>
          For cloud providers, you'll need an API key from the provider's dashboard.
        </p>
      </div>
    </div>
  );
}
