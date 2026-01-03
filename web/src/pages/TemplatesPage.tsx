import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, FileText, Settings, CheckCircle, AlertCircle, Upload, Loader2, Code, FormInput } from 'lucide-react';
import { templatesApi } from '../api/templates';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { useToast } from '../store/uiStore';
import { ResumeFormEditor } from '../components/templates/ResumeFormEditor';
import { RequirementsFormEditor } from '../components/templates/RequirementsFormEditor';
import type { ATSScoreResult } from '../types/template';
import clsx from 'clsx';

type Tab = 'resume' | 'requirements';
type ViewMode = 'form' | 'raw';

function ViewModeToggle({ mode, onChange }: { mode: ViewMode; onChange: (mode: ViewMode) => void }) {
  return (
    <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
      <button
        onClick={() => onChange('form')}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
          mode === 'form'
            ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
        )}
      >
        <FormInput className="w-4 h-4" />
        Form
      </button>
      <button
        onClick={() => onChange('raw')}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
          mode === 'raw'
            ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
        )}
      >
        <Code className="w-4 h-4" />
        Raw
      </button>
    </div>
  );
}

export function TemplatesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('resume');
  const [viewMode, setViewMode] = useState<ViewMode>('raw');
  const [resumeContent, setResumeContent] = useState('');
  const [requirementsContent, setRequirementsContent] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [atsScore, setAtsScore] = useState<ATSScoreResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const queryClient = useQueryClient();

  // Load resume
  const { data: resumeData, isLoading: loadingResume } = useQuery({
    queryKey: ['resume'],
    queryFn: templatesApi.getResume,
  });

  // Load requirements
  const { data: requirementsData, isLoading: loadingRequirements } = useQuery({
    queryKey: ['requirements'],
    queryFn: templatesApi.getRequirements,
  });

  // Sync resume content when data changes
  useEffect(() => {
    if (resumeData?.content) {
      setResumeContent(resumeData.content);
      setHasUnsavedChanges(false);
    }
  }, [resumeData?.content]);

  // Sync requirements content when data changes
  useEffect(() => {
    if (requirementsData?.content) {
      setRequirementsContent(requirementsData.content);
      setHasUnsavedChanges(false);
    }
  }, [requirementsData?.content]);

  // Validate templates
  const { data: validation } = useQuery({
    queryKey: ['template-validation'],
    queryFn: templatesApi.validate,
  });

  // Save resume
  const saveResumeMutation = useMutation({
    mutationFn: templatesApi.updateResume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resume'] });
      queryClient.invalidateQueries({ queryKey: ['template-validation'] });
      toast.success('Resume saved successfully');
      setHasUnsavedChanges(false);
    },
    onError: () => {
      toast.error('Failed to save resume');
    },
  });

  // Save requirements
  const saveRequirementsMutation = useMutation({
    mutationFn: templatesApi.updateRequirements,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
      queryClient.invalidateQueries({ queryKey: ['template-validation'] });
      toast.success('Requirements saved successfully');
      setHasUnsavedChanges(false);
    },
    onError: () => {
      toast.error('Failed to save requirements');
    },
  });

  // Upload resume
  const uploadResumeMutation = useMutation({
    mutationFn: templatesApi.uploadResume,
    onSuccess: (data) => {
      setResumeContent(data.content);
      queryClient.invalidateQueries({ queryKey: ['resume'] });
      queryClient.invalidateQueries({ queryKey: ['template-validation'] });
      toast.success(data.message);
      setHasUnsavedChanges(false);
      setAtsScore(null);
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to upload resume');
    },
  });

  // ATS Score
  const atsScoreMutation = useMutation({
    mutationFn: templatesApi.getATSScore,
    onSuccess: (data) => {
      setAtsScore(data);
      toast.success('ATS scoring complete');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to score resume');
    },
  });

  const handleSave = () => {
    if (activeTab === 'resume') {
      saveResumeMutation.mutate(resumeContent);
    } else {
      saveRequirementsMutation.mutate(requirementsContent);
    }
  };

  const handleResumeContentChange = (content: string) => {
    setResumeContent(content);
    setHasUnsavedChanges(true);
  };

  const handleRequirementsContentChange = (content: string) => {
    setRequirementsContent(content);
    setHasUnsavedChanges(true);
  };

  const handleFileSelect = (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      toast.error('Please upload a .docx file');
      return;
    }
    uploadResumeMutation.mutate(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (loadingResume || loadingRequirements) {
    return <LoadingPage message="Loading templates..." />;
  }

  const isSaving = saveResumeMutation.isPending || saveRequirementsMutation.isPending;
  const isUploading = uploadResumeMutation.isPending;
  const isScoring = atsScoreMutation.isPending;
  const currentValidation = activeTab === 'resume' ? validation?.resume : validation?.requirements;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Templates</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Edit your resume and job requirements</p>
        </div>
        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <span className="text-sm text-yellow-600 dark:text-yellow-500">Unsaved changes</span>
          )}
          <Button onClick={handleSave} disabled={!hasUnsavedChanges || isSaving} loading={isSaving}>
            <Save className="w-4 h-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('resume')}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'resume'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            )}
          >
            <FileText className="w-4 h-4" />
            Resume
            {validation?.resume && (
              validation.resume.valid ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-500" />
              )
            )}
          </button>
          <button
            onClick={() => setActiveTab('requirements')}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'requirements'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            )}
          >
            <Settings className="w-4 h-4" />
            Requirements
            {validation?.requirements && (
              validation.requirements.valid ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-500" />
              )
            )}
          </button>
        </nav>
      </div>

      {/* Resume Upload Section - Only show on resume tab */}
      {activeTab === 'resume' && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={clsx(
            'border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors',
            isDragging
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800'
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            onChange={handleFileInputChange}
            className="hidden"
          />
          <div className="flex items-center justify-center gap-3">
            {isUploading ? (
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
            ) : (
              <Upload className="w-5 h-5 text-gray-400" />
            )}
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {isUploading
                ? 'Uploading and extracting text...'
                : 'Drop a .docx file here or click to upload'}
            </span>
          </div>
        </div>
      )}

      {/* Validation Status */}
      {currentValidation && !currentValidation.valid && currentValidation.errors && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-700 dark:text-red-300 font-medium">
            <AlertCircle className="w-5 h-5" />
            Validation Errors
          </div>
          <ul className="mt-2 space-y-1">
            {currentValidation.errors.map((error, i) => (
              <li key={i} className="text-sm text-red-600 dark:text-red-400">- {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Main Content Area */}
      <div className="grid gap-6 grid-cols-1">
        {/* Editor Card */}
        <Card padding="none" className="overflow-hidden">
          {/* Editor Header */}
          <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {activeTab === 'resume' ? 'resume.txt' : 'requirements.yaml'}
            </span>
            <div className="flex items-center gap-3">
              {currentValidation?.size && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {(currentValidation.size / 1024).toFixed(1)} KB
                </span>
              )}
              <ViewModeToggle mode={viewMode} onChange={setViewMode} />
            </div>
          </div>

          {/* Editor Content */}
          {activeTab === 'resume' ? (
            viewMode === 'form' ? (
              <ResumeFormEditor
                content={resumeContent}
                onChange={handleResumeContentChange}
                onAnalyze={() => atsScoreMutation.mutate()}
                isAnalyzing={isScoring}
                atsScore={atsScore}
                onClearAtsScore={() => setAtsScore(null)}
              />
            ) : (
              <textarea
                value={resumeContent}
                onChange={(e) => handleResumeContentChange(e.target.value)}
                className="w-full h-[600px] p-4 font-mono text-sm resize-none focus:outline-none bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                placeholder="Paste your resume here or upload a .docx file..."
                spellCheck
              />
            )
          ) : (
            viewMode === 'form' ? (
              <RequirementsFormEditor
                content={requirementsContent}
                onChange={handleRequirementsContentChange}
              />
            ) : (
              <textarea
                value={requirementsContent}
                onChange={(e) => handleRequirementsContentChange(e.target.value)}
                className="w-full h-[600px] p-4 font-mono text-sm resize-none focus:outline-none bg-gray-900 text-gray-100"
                placeholder="Enter your requirements in YAML format..."
              />
            )
          )}
        </Card>
      </div>

      {/* Help Text */}
      <div className="text-sm text-gray-500 dark:text-gray-400">
        {activeTab === 'resume' ? (
          <p>
            Edit your resume in <strong>Raw</strong> view, then switch to <strong>Form</strong> view and click
            "Analyze Resume" to parse it into structured fields and get an ATS compatibility score.
          </p>
        ) : (
          <p>
            Use the <strong>Form</strong> view to easily configure your job search preferences, or switch to <strong>Raw</strong> view
            to edit the YAML configuration directly.
          </p>
        )}
      </div>
    </div>
  );
}
