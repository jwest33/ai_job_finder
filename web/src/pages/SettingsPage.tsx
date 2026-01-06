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
  FileText,
  ChevronDown,
  ChevronRight,
  Activity,
  Trash2,
  Clock,
  XCircle,
} from 'lucide-react';
import { aiApi } from '../api/ai';
import { settingsApi, type LLMTrace } from '../api/settings';
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

  // Prompt configuration state
  const [showPromptConfig, setShowPromptConfig] = useState(false);
  const [activePromptSection, setActivePromptSection] = useState<
    'resume' | 'cover-letter' | 'match-scorer' | 'gap-analyzer' | 'resume-optimizer' | null
  >(null);
  const [editingPrompt, setEditingPrompt] = useState('');
  const [editingTemp, setEditingTemp] = useState(0.3);

  // Tracing state
  const [showTracing, setShowTracing] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<LLMTrace | null>(null);

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

  // Load prompt configuration
  const { data: promptConfig, refetch: refetchPrompts } = useQuery({
    queryKey: ['prompt-config'],
    queryFn: settingsApi.getPromptConfig,
    enabled: showPromptConfig,
  });

  // Load traces
  const { data: tracesData, refetch: refetchTraces } = useQuery({
    queryKey: ['llm-traces'],
    queryFn: () => settingsApi.getTraces({ limit: 50 }),
    enabled: showTracing,
    refetchInterval: showTracing ? 5000 : false, // Auto-refresh when visible
  });

  // Sync form state when settings load
  useEffect(() => {
    if (settings) {
      setBaseUrl(settings.base_url);
      setApiKey(''); // Don't show masked key in input
      setModel(settings.model);
      setVisionModel(settings.vision_model || '');
      setVisionEnabled(settings.vision_enabled ?? null);
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

  // Threshold save mutation
  const saveThresholdsMutation = useMutation({
    mutationFn: (update: ThresholdSettingsUpdate) => aiApi.updateThresholds(update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['threshold-settings'] });
      queryClient.invalidateQueries({ queryKey: ['job-stats'] });
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
      queryClient.invalidateQueries({ queryKey: ['job-stats'] });
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

  // Prompt configuration handlers
  const handleSavePrompt = async (
    section: 'resume' | 'cover-letter' | 'match-scorer' | 'gap-analyzer' | 'resume-optimizer'
  ) => {
    try {
      if (section === 'resume') {
        await settingsApi.updateResumeRewriter({
          system_prompt: editingPrompt,
          parameters: { temperature: editingTemp },
        });
      } else if (section === 'cover-letter') {
        await settingsApi.updateCoverLetter({
          system_prompt: editingPrompt,
          parameters: { temperature: editingTemp },
        });
      } else if (section === 'match-scorer') {
        await settingsApi.updateMatchScorer({
          system_prompt: editingPrompt,
          parameters: { temperature: editingTemp },
        });
      } else if (section === 'gap-analyzer') {
        await settingsApi.updateGapAnalyzer({
          system_prompt: editingPrompt,
          parameters: { temperature: editingTemp },
        });
      } else if (section === 'resume-optimizer') {
        await settingsApi.updateResumeOptimizer({
          system_prompt: editingPrompt,
          parameters: { temperature: editingTemp },
        });
      }
      toast.success('Prompt saved successfully');
      refetchPrompts();
      setActivePromptSection(null);
    } catch {
      toast.error('Failed to save prompt');
    }
  };

  const handleResetPrompts = async () => {
    try {
      await settingsApi.resetToDefaults();
      toast.success('Prompts reset to defaults');
      refetchPrompts();
    } catch {
      toast.error('Failed to reset prompts');
    }
  };

  const handleClearTraces = async () => {
    try {
      await settingsApi.clearTraces();
      toast.success('Traces cleared');
      refetchTraces();
    } catch {
      toast.error('Failed to clear traces');
    }
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI Settings</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Configure your AI provider for job matching and analysis</p>
        </div>
        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <span className="text-sm text-yellow-600 dark:text-yellow-500">Unsaved changes</span>
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
              ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
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
                testResult.success ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'
              )}
            >
              {testResult.success ? 'Connection Successful' : 'Connection Failed'}
            </span>
          </div>
          {testResult.success && (
            <div className="mt-2 text-sm text-green-600 dark:text-green-400 space-y-1">
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
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">{testResult.error}</p>
          )}
        </div>
      )}

      {/* Presets */}
      {presets && presets.length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Quick Setup</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {presets.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handlePresetClick(preset)}
                className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="font-medium text-sm text-gray-900 dark:text-white">{preset.name}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
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
            <Cpu className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Provider Settings</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                OpenAI-compatible endpoint (e.g., llama-server, Ollama, OpenAI)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                  className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  {showApiKey ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Required for cloud providers (OpenAI, Anthropic)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Model name/ID (e.g., gpt-4o, llama3.2, default)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Vision</label>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setVisionEnabled(null);
                    markChanged();
                  }}
                  className={clsx(
                    'px-3 py-1 text-sm rounded-lg border',
                    visionEnabled === null
                      ? 'bg-blue-100 dark:bg-blue-900/50 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                      : 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
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
                      ? 'bg-green-100 dark:bg-green-900/50 border-green-300 dark:border-green-700 text-green-700 dark:text-green-300'
                      : 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
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
                      ? 'bg-red-100 dark:bg-red-900/50 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                      : 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
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
            <Settings className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Generation Settings</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>Precise (0)</span>
                <span>Creative (2)</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Maximum tokens to generate per response
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
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
            <Target className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Match Quality Thresholds</h2>
          </div>
          <div className="flex items-center gap-3">
            {hasUnsavedThresholds && (
              <span className="text-sm text-yellow-600 dark:text-yellow-500">Unsaved changes</span>
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

        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Configure score thresholds that determine job match quality ratings.
          Jobs are rated based on where their score falls relative to these thresholds.
        </p>

        {thresholdError && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
            {thresholdError}
          </div>
        )}

        <div className="space-y-6">
          {/* Excellent threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
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
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Scores at or above this value are rated "Excellent"
            </p>
          </div>

          {/* Good threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
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
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Scores at or above this value (but below Excellent) are rated "Good"
            </p>
          </div>

          {/* Fair threshold */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
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
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Scores at or above this value (but below Good) are rated "Fair"
            </p>
          </div>

          {/* Preview */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Preview</h3>
            <div className="flex gap-4 text-sm text-gray-700 dark:text-gray-300">
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
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div>
            <h3 className="font-medium text-gray-900 dark:text-white">Reset Thresholds</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
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

      {/* Prompt Configuration */}
      <Card>
        <button
          onClick={() => setShowPromptConfig(!showPromptConfig)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Prompt Configuration</h2>
          </div>
          {showPromptConfig ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
        </button>

        {showPromptConfig && (
          <div className="mt-4 space-y-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Customize the system prompts and parameters for resume tailoring and cover letter generation.
            </p>

            {/* Resume Rewriter Section */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <button
                onClick={() => {
                  if (activePromptSection === 'resume') {
                    setActivePromptSection(null);
                  } else {
                    setActivePromptSection('resume');
                    setEditingPrompt(promptConfig?.resume_rewriter.system_prompt || '');
                    setEditingTemp(promptConfig?.resume_rewriter.parameters.temperature || 0.3);
                  }
                }}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
              >
                <span className="font-medium text-gray-900 dark:text-white">Resume Tailoring</span>
                <span className="text-xs text-gray-500">
                  temp: {promptConfig?.resume_rewriter.parameters.temperature || 0.3}
                </span>
              </button>

              {activePromptSection === 'resume' && (
                <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      rows={8}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Temperature: {editingTemp.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editingTemp}
                      onChange={(e) => setEditingTemp(parseFloat(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setActivePromptSection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={() => handleSavePrompt('resume')}>
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Cover Letter Section */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <button
                onClick={() => {
                  if (activePromptSection === 'cover-letter') {
                    setActivePromptSection(null);
                  } else {
                    setActivePromptSection('cover-letter');
                    setEditingPrompt(promptConfig?.cover_letter.system_prompt || '');
                    setEditingTemp(promptConfig?.cover_letter.parameters.temperature || 0.5);
                  }
                }}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
              >
                <span className="font-medium text-gray-900 dark:text-white">Cover Letter Generation</span>
                <span className="text-xs text-gray-500">
                  temp: {promptConfig?.cover_letter.parameters.temperature || 0.5}
                </span>
              </button>

              {activePromptSection === 'cover-letter' && (
                <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      rows={8}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Temperature: {editingTemp.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editingTemp}
                      onChange={(e) => setEditingTemp(parseFloat(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setActivePromptSection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={() => handleSavePrompt('cover-letter')}>
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Matching Pipeline Section Header */}
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Job Matching Pipeline
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Customize the prompts used in the 3-pass job matching pipeline.
              </p>
            </div>

            {/* Match Scorer Section */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <button
                onClick={() => {
                  if (activePromptSection === 'match-scorer') {
                    setActivePromptSection(null);
                  } else {
                    setActivePromptSection('match-scorer');
                    setEditingPrompt(promptConfig?.match_scorer.system_prompt || '');
                    setEditingTemp(promptConfig?.match_scorer.parameters.temperature || 0.2);
                  }
                }}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">Job Scoring (Pass 1)</span>
                  <span className="text-xs bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded">
                    Scoring
                  </span>
                </div>
                <span className="text-xs text-gray-500">
                  temp: {promptConfig?.match_scorer.parameters.temperature || 0.2}
                </span>
              </button>

              {activePromptSection === 'match-scorer' && (
                <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      rows={12}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Temperature: {editingTemp.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editingTemp}
                      onChange={(e) => setEditingTemp(parseFloat(e.target.value))}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Lower temperature (0.1-0.3) recommended for consistent scoring
                    </p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setActivePromptSection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={() => handleSavePrompt('match-scorer')}>
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Gap Analyzer Section */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <button
                onClick={() => {
                  if (activePromptSection === 'gap-analyzer') {
                    setActivePromptSection(null);
                  } else {
                    setActivePromptSection('gap-analyzer');
                    setEditingPrompt(promptConfig?.gap_analyzer.system_prompt || '');
                    setEditingTemp(promptConfig?.gap_analyzer.parameters.temperature || 0.4);
                  }
                }}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">Gap Analysis (Pass 2)</span>
                  <span className="text-xs bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300 px-2 py-0.5 rounded">
                    Analysis
                  </span>
                </div>
                <span className="text-xs text-gray-500">
                  temp: {promptConfig?.gap_analyzer.parameters.temperature || 0.4}
                </span>
              </button>

              {activePromptSection === 'gap-analyzer' && (
                <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      rows={12}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Temperature: {editingTemp.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editingTemp}
                      onChange={(e) => setEditingTemp(parseFloat(e.target.value))}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Moderate temperature (0.3-0.5) for balanced analysis
                    </p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setActivePromptSection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={() => handleSavePrompt('gap-analyzer')}>
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Resume Optimizer Section */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
              <button
                onClick={() => {
                  if (activePromptSection === 'resume-optimizer') {
                    setActivePromptSection(null);
                  } else {
                    setActivePromptSection('resume-optimizer');
                    setEditingPrompt(promptConfig?.resume_optimizer.system_prompt || '');
                    setEditingTemp(promptConfig?.resume_optimizer.parameters.temperature || 0.5);
                  }
                }}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">Resume Optimization (Pass 3)</span>
                  <span className="text-xs bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 px-2 py-0.5 rounded">
                    Suggestions
                  </span>
                </div>
                <span className="text-xs text-gray-500">
                  temp: {promptConfig?.resume_optimizer.parameters.temperature || 0.5}
                </span>
              </button>

              {activePromptSection === 'resume-optimizer' && (
                <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      System Prompt
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      rows={12}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Temperature: {editingTemp.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editingTemp}
                      onChange={(e) => setEditingTemp(parseFloat(e.target.value))}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Higher temperature (0.4-0.6) for creative recommendations
                    </p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setActivePromptSection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={() => handleSavePrompt('resume-optimizer')}>
                      <Save className="w-4 h-4 mr-1" />
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Reset Prompts */}
            <div className="flex justify-end pt-2">
              <Button size="sm" variant="secondary" onClick={handleResetPrompts}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Reset All Prompts to Defaults
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* LLM Tracing */}
      <Card>
        <button
          onClick={() => setShowTracing(!showTracing)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">LLM Tracing</h2>
            {tracesData?.stats && (
              <span className="text-xs bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded">
                {tracesData.stats.total_traces} traces
              </span>
            )}
          </div>
          {showTracing ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
        </button>

        {showTracing && (
          <div className="mt-4 space-y-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              View recent LLM calls for debugging and prompt tuning.
            </p>

            {/* Stats */}
            {tracesData?.stats && (
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {tracesData.stats.total_traces}
                  </div>
                  <div className="text-xs text-gray-500">Total</div>
                </div>
                <div className="bg-green-50 dark:bg-green-900/30 p-3 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {(tracesData.stats.success_rate || 0).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-500">Success</div>
                </div>
                <div className="bg-red-50 dark:bg-red-900/30 p-3 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {tracesData.stats.failed_traces}
                  </div>
                  <div className="text-xs text-gray-500">Failed</div>
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-900/30 p-3 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-600">
                    {(tracesData.stats.avg_retries || 0).toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-500">Avg Retries</div>
                </div>
              </div>
            )}

            {/* Trace List */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
              {tracesData?.traces.length === 0 && (
                <div className="p-4 text-center text-gray-500">No traces recorded yet</div>
              )}
              {tracesData?.traces.map((trace) => (
                <button
                  key={trace.id}
                  onClick={() => setSelectedTrace(selectedTrace?.id === trace.id ? null : trace)}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {trace.validation_passed ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                      <span className="font-medium text-sm text-gray-900 dark:text-white">
                        {trace.operation}
                      </span>
                      {trace.retry_count > 0 && (
                        <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 rounded">
                          {trace.retry_count} retries
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      {trace.duration_ms && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {(trace.duration_ms / 1000).toFixed(1)}s
                        </span>
                      )}
                      <span>{new Date(trace.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                  {trace.job_title && (
                    <div className="text-xs text-gray-500 mt-1">
                      {trace.job_title} {trace.job_company && `at ${trace.job_company}`}
                    </div>
                  )}

                  {/* Expanded trace details */}
                  {selectedTrace?.id === trace.id && (
                    <div className="mt-3 space-y-2 border-t border-gray-200 dark:border-gray-600 pt-3">
                      <div>
                        <div className="text-xs font-medium text-gray-500 mb-1">System Prompt</div>
                        <pre className="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto whitespace-pre-wrap max-h-32">
                          {trace.system_prompt || '(none)'}
                        </pre>
                      </div>
                      {trace.validation_errors.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-red-500 mb-1">Validation Errors</div>
                          <ul className="text-xs text-red-600 list-disc list-inside">
                            {trace.validation_errors.map((err, i) => (
                              <li key={i}>{err}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </button>
              ))}
            </div>

            {/* Clear Traces */}
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="secondary"
                onClick={handleClearTraces}
                disabled={!tracesData?.traces.length}
              >
                <Trash2 className="w-4 h-4 mr-1" />
                Clear All Traces
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Actions */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900 dark:text-white">Reset AI Settings</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
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
      <div className="text-sm text-gray-500 dark:text-gray-400 space-y-2">
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
