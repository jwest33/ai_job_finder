import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, FileText, Settings, CheckCircle, AlertCircle } from 'lucide-react';
import { templatesApi } from '../api/templates';
import { Card, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { useToast } from '../store/uiStore';
import clsx from 'clsx';

type Tab = 'resume' | 'requirements';

export function TemplatesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('resume');
  const [resumeContent, setResumeContent] = useState('');
  const [requirementsContent, setRequirementsContent] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
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

  const handleSave = () => {
    if (activeTab === 'resume') {
      saveResumeMutation.mutate(resumeContent);
    } else {
      saveRequirementsMutation.mutate(requirementsContent);
    }
  };

  const handleContentChange = (content: string) => {
    if (activeTab === 'resume') {
      setResumeContent(content);
    } else {
      setRequirementsContent(content);
    }
    setHasUnsavedChanges(true);
  };

  if (loadingResume || loadingRequirements) {
    return <LoadingPage message="Loading templates..." />;
  }

  const isSaving = saveResumeMutation.isPending || saveRequirementsMutation.isPending;
  const currentContent = activeTab === 'resume' ? resumeContent : requirementsContent;
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

      {/* Validation Status */}
      {currentValidation && !currentValidation.valid && currentValidation.errors && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-700 font-medium">
            <AlertCircle className="w-5 h-5" />
            Validation Errors
          </div>
          <ul className="mt-2 space-y-1">
            {currentValidation.errors.map((error, i) => (
              <li key={i} className="text-sm text-red-600">• {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Editor */}
      <Card padding="none" className="overflow-hidden">
        <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">
            {activeTab === 'resume' ? 'resume.txt' : 'requirements.yaml'}
          </span>
          {currentValidation?.size && (
            <span className="text-xs text-gray-500">
              {(currentValidation.size / 1024).toFixed(1)} KB
            </span>
          )}
        </div>
        <textarea
          value={currentContent}
          onChange={(e) => handleContentChange(e.target.value)}
          className={clsx(
            'w-full h-[600px] p-4 font-mono text-sm resize-none focus:outline-none',
            activeTab === 'requirements' && 'bg-gray-900 text-gray-100'
          )}
          placeholder={
            activeTab === 'resume'
              ? 'Paste your resume here...'
              : 'Enter your requirements in YAML format...'
          }
          spellCheck={activeTab === 'resume'}
        />
      </Card>

      {/* Help Text */}
      <div className="text-sm text-gray-500">
        {activeTab === 'resume' ? (
          <p>
            Enter your resume in plain text format. This will be used by the AI to match your
            skills and experience against job postings.
          </p>
        ) : (
          <div className="space-y-2">
            <p>Enter your job requirements in YAML format. Example structure:</p>
            <pre className="bg-gray-100 p-3 rounded-lg text-xs overflow-x-auto">
{`candidate_profile:
  self_description: "Senior software engineer..."
  key_strengths:
    - Python
    - Machine Learning
  must_haves:
    - Remote work
    - Competitive salary

job_requirements:
  target_roles:
    - Software Engineer
    - ML Engineer
  required_skills:
    - Python
    - SQL

preferences:
  remote_preference: "remote"
  salary_range:
    min: 150000
    max: 250000`}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
