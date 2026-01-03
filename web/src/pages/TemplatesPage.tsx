import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, FileText, Settings, CheckCircle, AlertCircle, Upload, Zap, ChevronDown, ChevronUp, Loader2, Code, FormInput } from 'lucide-react';
import { templatesApi } from '../api/templates';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { useToast } from '../store/uiStore';
import { ResumeFormEditor } from '../components/templates/ResumeFormEditor';
import { RequirementsFormEditor } from '../components/templates/RequirementsFormEditor';
import type { ATSScoreResult, ATSCategoryResult } from '../types/template';
import clsx from 'clsx';

type Tab = 'resume' | 'requirements';
type ViewMode = 'form' | 'raw';

const CATEGORY_LABELS: Record<string, string> = {
  keywords: 'Keywords',
  formatting: 'Formatting',
  sections: 'Section Structure',
  achievements: 'Achievements',
  contact_info: 'Contact Info',
  skills: 'Skills',
};

function getScoreColor(score: number): string {
  if (score >= 90) return 'text-green-600';
  if (score >= 70) return 'text-blue-600';
  if (score >= 50) return 'text-yellow-600';
  return 'text-red-600';
}

function getScoreBgColor(score: number): string {
  if (score >= 90) return 'bg-green-500';
  if (score >= 70) return 'bg-blue-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function ATSCategoryCard({ name, data }: { name: string; data: ATSCategoryResult }) {
  const [expanded, setExpanded] = useState(false);
  const hasIssues = data.issues.length > 0;
  const hasRecommendations = data.recommendations.length > 0;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700">{CATEGORY_LABELS[name] || name}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full', getScoreBgColor(data.score))}
                style={{ width: `${data.score}%` }}
              />
            </div>
            <span className={clsx('text-sm font-bold w-8', getScoreColor(data.score))}>
              {data.score}
            </span>
          </div>
          {(hasIssues || hasRecommendations) && (
            expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>
      {expanded && (hasIssues || hasRecommendations) && (
        <div className="px-3 pb-3 space-y-3">
          {hasIssues && (
            <div>
              <h4 className="text-xs font-medium text-red-600 uppercase mb-1">Issues</h4>
              <ul className="space-y-1">
                {data.issues.map((issue, i) => (
                  <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                    <span className="text-red-400 mt-0.5">-</span>
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasRecommendations && (
            <div>
              <h4 className="text-xs font-medium text-blue-600 uppercase mb-1">Recommendations</h4>
              <ul className="space-y-1">
                {data.recommendations.map((rec, i) => (
                  <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">+</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ATSScorePanel({ score, onClose }: { score: ATSScoreResult; onClose: () => void }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">ATS Quality Score</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">
          &times;
        </button>
      </div>

      <div className="p-4 space-y-4 max-h-[550px] overflow-y-auto">
        {/* Overall Score */}
        <div className="text-center py-4">
          <div className={clsx('text-5xl font-bold', getScoreColor(score.overall_score))}>
            {score.overall_score}
          </div>
          <div className="text-sm text-gray-500 mt-1">out of 100</div>
        </div>

        {/* Summary */}
        <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
          {score.summary}
        </p>

        {/* Category Breakdown */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Category Scores</h4>
          <div className="space-y-2">
            {Object.entries(score.categories).map(([name, data]) => (
              <ATSCategoryCard key={name} name={name} data={data} />
            ))}
          </div>
        </div>

        {/* Top Recommendations */}
        {score.top_recommendations.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Top Recommendations</h4>
            <ul className="space-y-2">
              {score.top_recommendations.map((rec, i) => (
                <li key={i} className="text-sm text-gray-600 flex items-start gap-2 bg-blue-50 p-2 rounded">
                  <span className="text-blue-500 font-bold">{i + 1}.</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function ViewModeToggle({ mode, onChange }: { mode: ViewMode; onChange: (mode: ViewMode) => void }) {
  return (
    <div className="flex bg-gray-100 rounded-lg p-0.5">
      <button
        onClick={() => onChange('form')}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
          mode === 'form'
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
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
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
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
  const [viewMode, setViewMode] = useState<ViewMode>('form');
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
          <h1 className="text-2xl font-bold text-gray-900">Templates</h1>
          <p className="text-gray-500 mt-1">Edit your resume and job requirements</p>
        </div>
        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <span className="text-sm text-yellow-600">Unsaved changes</span>
          )}
          <Button onClick={handleSave} disabled={!hasUnsavedChanges || isSaving} loading={isSaving}>
            <Save className="w-4 h-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('resume')}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'resume'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
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
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
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
        <div className="flex gap-4">
          {/* Upload Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={clsx(
              'flex-1 border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors',
              isDragging
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
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
              <span className="text-sm text-gray-600">
                {isUploading
                  ? 'Uploading and extracting text...'
                  : 'Drop a .docx file here or click to upload'}
              </span>
            </div>
          </div>

          {/* ATS Score Button */}
          <Button
            variant="secondary"
            onClick={() => atsScoreMutation.mutate()}
            disabled={isScoring || !resumeContent}
            loading={isScoring}
          >
            <Zap className="w-4 h-4 mr-2" />
            {isScoring ? 'Analyzing...' : 'ATS Score'}
          </Button>
        </div>
      )}

      {/* Validation Status */}
      {currentValidation && !currentValidation.valid && currentValidation.errors && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-700 font-medium">
            <AlertCircle className="w-5 h-5" />
            Validation Errors
          </div>
          <ul className="mt-2 space-y-1">
            {currentValidation.errors.map((error, i) => (
              <li key={i} className="text-sm text-red-600">- {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Main Content Area */}
      <div className={clsx('grid gap-6', activeTab === 'resume' && atsScore ? 'grid-cols-2' : 'grid-cols-1')}>
        {/* Editor Card */}
        <Card padding="none" className="overflow-hidden">
          {/* Editor Header */}
          <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">
              {activeTab === 'resume' ? 'resume.txt' : 'requirements.yaml'}
            </span>
            <div className="flex items-center gap-3">
              {currentValidation?.size && (
                <span className="text-xs text-gray-500">
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
              />
            ) : (
              <textarea
                value={resumeContent}
                onChange={(e) => handleResumeContentChange(e.target.value)}
                className="w-full h-[600px] p-4 font-mono text-sm resize-none focus:outline-none"
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

        {/* ATS Score Panel */}
        {activeTab === 'resume' && atsScore && (
          <ATSScorePanel score={atsScore} onClose={() => setAtsScore(null)} />
        )}
      </div>

      {/* Help Text */}
      <div className="text-sm text-gray-500">
        {activeTab === 'resume' ? (
          <p>
            Use the <strong>Form</strong> view to edit your resume with structured fields, or switch to <strong>Raw</strong> view
            to edit the plain text directly. Upload a .docx file to import your resume, then use ATS Score to analyze it.
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
