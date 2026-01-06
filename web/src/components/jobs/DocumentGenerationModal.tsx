import { useState, useEffect } from 'react';
import {
  FileText,
  Mail,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
  Save,
  Download,
  GitCompare,
  FileOutput,
  RefreshCw,
  Upload,
  Clock,
  ToggleLeft,
  ToggleRight,
  RotateCcw,
  MessageSquare,
  X,
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { documentsApi, type TailoredDocument } from '../../api/documents';
import type { Job } from '../../types/job';
import type {
  ResumeRewriteResponse,
  CoverLetterResponse,
  VerificationStatus,
  RewrittenResume,
  VerificationReport,
} from '../../types/document';

type DocumentType = 'resume' | 'cover-letter';

interface DocumentGenerationModalProps {
  isOpen: boolean;
  onClose: () => void;
  job: Job;
  documentType: DocumentType;
}

export function DocumentGenerationModal({
  isOpen,
  onClose,
  job,
  documentType,
}: DocumentGenerationModalProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resumeResult, setResumeResult] = useState<ResumeRewriteResponse | null>(null);
  const [coverLetterResult, setCoverLetterResult] = useState<CoverLetterResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showChanges, setShowChanges] = useState(false);

  // Section selection state: tracks which version (original vs rewritten) to use per item
  // Keys: 'summary', 'experience-{expIdx}-bullet-{bulletIdx}', 'skills'
  // Values: 'original' | 'rewritten'
  const [sectionSelections, setSectionSelections] = useState<Record<string, 'original' | 'rewritten'>>({});

  // Regeneration state
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(null);
  const [regenerateInstructions, setRegenerateInstructions] = useState('');
  const [showRegenerateModal, setShowRegenerateModal] = useState<string | null>(null);

  // Saved document state
  const [isLoadingSaved, setIsLoadingSaved] = useState(false);
  const [savedDocument, setSavedDocument] = useState<TailoredDocument | null>(null);

  // Cover letter options
  const [tone, setTone] = useState<'professional' | 'enthusiastic' | 'formal'>('professional');
  const [maxWords, setMaxWords] = useState(400);

  // Cover letter template
  const [showTemplateUpload, setShowTemplateUpload] = useState(false);
  const [templateContent, setTemplateContent] = useState('');
  const [uploadingTemplate, setUploadingTemplate] = useState(false);

  // Check for saved document when modal opens
  useEffect(() => {
    if (isOpen && job) {
      checkForSavedDocument();
    }
  }, [isOpen, job?.job_url, documentType]);

  const checkForSavedDocument = async () => {
    setIsLoadingSaved(true);
    setSavedDocument(null);
    try {
      const docType = documentType === 'cover-letter' ? 'cover_letter' : 'resume';
      const saved = await documentsApi.getTailoredDocument(docType, job.job_url);
      if (saved.found) {
        setSavedDocument(saved);
        // Also populate the result states so the UI shows the saved document
        if (documentType === 'resume' && saved.structured_data) {
          setResumeResult({
            success: true,
            rewritten_resume: saved.structured_data as unknown as RewrittenResume,
            verification: saved.verification_data as unknown as VerificationReport,
            plain_text: saved.plain_text,
          });
        } else if (documentType === 'cover-letter' && saved.plain_text) {
          setCoverLetterResult({
            success: true,
            plain_text: saved.plain_text,
          });
        }
      }
    } catch (err) {
      console.error('Failed to check for saved document:', err);
    } finally {
      setIsLoadingSaved(false);
    }
  };

  // Initialize section selections when resume result is available (default all to 'rewritten')
  useEffect(() => {
    if (resumeResult?.rewritten_resume) {
      const initial: Record<string, 'original' | 'rewritten'> = {
        summary: 'rewritten',
        skills: 'rewritten',
      };
      // Initialize individual bullet selections
      resumeResult.rewritten_resume.experience.forEach((exp, expIdx) => {
        exp.original_bullets.forEach((_, bulletIdx) => {
          initial[`experience-${expIdx}-bullet-${bulletIdx}`] = 'rewritten';
        });
      });
      setSectionSelections(initial);
    }
  }, [resumeResult]);

  // Toggle a section between original and rewritten
  const toggleSection = (sectionKey: string) => {
    setSectionSelections(prev => ({
      ...prev,
      [sectionKey]: prev[sectionKey] === 'rewritten' ? 'original' : 'rewritten',
    }));
  };

  // Build plain text based on current section selections (supports per-bullet selection)
  const buildCustomPlainText = (): string => {
    if (!resumeResult?.rewritten_resume) return '';

    const resume = resumeResult.rewritten_resume;
    const lines: string[] = [];

    // Contact info (always from rewritten - immutable)
    lines.push(resume.contact.name);
    lines.push(resume.contact.email);
    if (resume.contact.phone) lines.push(resume.contact.phone);
    if (resume.contact.location) lines.push(resume.contact.location);
    if (resume.contact.linkedin) lines.push(resume.contact.linkedin);
    if (resume.contact.github) lines.push(resume.contact.github);
    lines.push('');

    // Summary
    if (resume.summary) {
      lines.push('SUMMARY');
      lines.push('-'.repeat(40));
      const summaryText = sectionSelections.summary === 'original'
        ? resume.summary.original
        : resume.summary.rewritten;
      lines.push(summaryText);
      lines.push('');
    }

    // Experience (with per-bullet selection support)
    lines.push('EXPERIENCE');
    lines.push('-'.repeat(40));
    resume.experience.forEach((exp, expIdx) => {
      lines.push(`${exp.title} | ${exp.company}`);
      lines.push(`${exp.start_date} - ${exp.end_date}${exp.location ? ` | ${exp.location}` : ''}`);
      // Select each bullet individually based on per-bullet selections
      exp.original_bullets.forEach((originalBullet, bulletIdx) => {
        const bulletKey = `experience-${expIdx}-bullet-${bulletIdx}`;
        const useOriginal = sectionSelections[bulletKey] === 'original';
        const bulletText = useOriginal ? originalBullet : (exp.rewritten_bullets[bulletIdx] || originalBullet);
        lines.push(`• ${bulletText}`);
      });
      lines.push('');
    });

    // Skills
    if (resume.skills) {
      lines.push('SKILLS');
      lines.push('-'.repeat(40));
      const skills = sectionSelections.skills === 'original'
        ? resume.skills.original_skills
        : resume.skills.rewritten_skills;
      lines.push(skills.join(', '));
      lines.push('');
    }

    // Education
    if (resume.education.length > 0) {
      lines.push('EDUCATION');
      lines.push('-'.repeat(40));
      resume.education.forEach(edu => {
        lines.push(`${edu.degree} - ${edu.school}${edu.year ? ` (${edu.year})` : ''}`);
      });
      lines.push('');
    }

    // Certifications
    if (resume.certifications.length > 0) {
      lines.push('CERTIFICATIONS');
      lines.push('-'.repeat(40));
      resume.certifications.forEach(cert => lines.push(`• ${cert}`));
      lines.push('');
    }

    return lines.join('\n');
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setResumeResult(null);
    setCoverLetterResult(null);

    try {
      if (documentType === 'resume') {
        const result = await documentsApi.rewriteResume({
          job_url: job.job_url,
        });
        if (result.success) {
          setResumeResult(result);
        } else {
          setError(result.error || 'Failed to rewrite resume');
        }
      } else {
        const result = await documentsApi.generateCoverLetter({
          job_url: job.job_url,
          tone,
          max_words: maxWords,
        });
        if (result.success) {
          setCoverLetterResult(result);
        } else {
          setError(result.error || 'Failed to generate cover letter');
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = async () => {
    let text: string | undefined;

    if (documentType === 'resume') {
      // Use custom builder if we have structured data (allows per-section selection)
      text = resumeResult?.rewritten_resume
        ? buildCustomPlainText()
        : resumeResult?.plain_text;
    } else {
      text = coverLetterResult?.plain_text;
    }

    if (text) {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSaveCoverLetter = async () => {
    if (!coverLetterResult?.plain_text) return;

    setSaving(true);
    try {
      await documentsApi.saveCoverLetter(job.job_url, coverLetterResult.plain_text);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save cover letter');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = () => {
    let text: string | undefined;

    if (documentType === 'resume') {
      // Use custom builder if we have structured data (allows per-section selection)
      text = resumeResult?.rewritten_resume
        ? buildCustomPlainText()
        : resumeResult?.plain_text;
    } else {
      text = coverLetterResult?.plain_text;
    }

    if (!text) return;

    const filename = documentType === 'resume'
      ? `resume_${job.company.replace(/\s+/g, '_')}_${job.title.replace(/\s+/g, '_')}.txt`
      : `cover_letter_${job.company.replace(/\s+/g, '_')}.txt`;

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    setResumeResult(null);
    setCoverLetterResult(null);
    setError(null);
    setCopied(false);
    setSaved(false);
    setShowChanges(false);
    setSavedDocument(null);
    setShowTemplateUpload(false);
    setTemplateContent('');
    setSectionSelections({});
    setRegeneratingSection(null);
    setRegenerateInstructions('');
    setShowRegenerateModal(null);
    onClose();
  };

  const handleRegenerate = async () => {
    // Clear saved document state to force regeneration
    setSavedDocument(null);
    setResumeResult(null);
    setCoverLetterResult(null);
    // Trigger generation
    await handleGenerate();
  };

  const handleUploadTemplate = async () => {
    if (!templateContent.trim()) return;
    setUploadingTemplate(true);
    try {
      await documentsApi.uploadCoverLetterTemplate(templateContent);
      setShowTemplateUpload(false);
      setTemplateContent('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload template');
    } finally {
      setUploadingTemplate(false);
    }
  };

  // Handle section regeneration with user instructions
  const handleRegenerateSection = async (sectionType: 'summary' | 'experience' | 'skills', sectionIndex?: number) => {
    if (!regenerateInstructions.trim()) {
      setError('Please provide instructions for what to improve');
      return;
    }

    const sectionKey = sectionIndex !== undefined
      ? `${sectionType}-${sectionIndex}`
      : sectionType;

    setRegeneratingSection(sectionKey);
    setShowRegenerateModal(null);

    try {
      const result = await documentsApi.regenerateSection({
        job_url: job.job_url,
        section_type: sectionType,
        section_index: sectionIndex,
        instructions: regenerateInstructions,
      });

      if (result.success && result.rewritten_section) {
        const rewrittenSection = result.rewritten_section;
        // Update the resume result with the new section
        setResumeResult(prev => {
          if (!prev?.rewritten_resume) return prev;

          const updated = { ...prev.rewritten_resume };

          if (sectionType === 'summary' && rewrittenSection.summary) {
            updated.summary = rewrittenSection.summary;
          } else if (sectionType === 'experience' && sectionIndex !== undefined && rewrittenSection.experience) {
            updated.experience = [...updated.experience];
            updated.experience[sectionIndex] = rewrittenSection.experience;
          } else if (sectionType === 'skills' && rewrittenSection.skills) {
            updated.skills = rewrittenSection.skills;
          }

          return {
            ...prev,
            rewritten_resume: updated,
          };
        });

        // Reset selections for regenerated section to use rewritten
        if (sectionType === 'experience' && sectionIndex !== undefined && resumeResult?.rewritten_resume) {
          const exp = resumeResult.rewritten_resume.experience[sectionIndex];
          const newSelections: Record<string, 'original' | 'rewritten'> = {};
          exp.original_bullets.forEach((_, bulletIdx) => {
            newSelections[`experience-${sectionIndex}-bullet-${bulletIdx}`] = 'rewritten';
          });
          setSectionSelections(prev => ({ ...prev, ...newSelections }));
        } else {
          setSectionSelections(prev => ({ ...prev, [sectionType]: 'rewritten' }));
        }
      } else {
        setError(result.error || 'Failed to regenerate section');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate section');
    } finally {
      setRegeneratingSection(null);
      setRegenerateInstructions('');
    }
  };

  // Open regenerate modal for a section
  const openRegenerateModal = (sectionType: string, sectionIndex?: number) => {
    const key = sectionIndex !== undefined ? `${sectionType}-${sectionIndex}` : sectionType;
    setShowRegenerateModal(key);
    setRegenerateInstructions('');
  };

  const getVerificationIcon = (status: VerificationStatus) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const getVerificationColor = (status: VerificationStatus) => {
    switch (status) {
      case 'passed':
        return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800';
      case 'warning':
        return 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800';
      case 'failed':
        return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800';
    }
  };

  const hasResult = resumeResult || coverLetterResult;
  const plainText = resumeResult?.plain_text || coverLetterResult?.plain_text;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={documentType === 'resume' ? 'Tailored Resume' : 'Cover Letter'}
      size="3xl"
    >
      <div className="space-y-4">
        {/* Job Info Header */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {documentType === 'resume' ? 'Tailoring resume for:' : 'Generating cover letter for:'}
          </p>
          <p className="font-medium text-gray-900 dark:text-white">
            {job.title} at {job.company}
          </p>
        </div>

        {/* Loading state when checking for saved document */}
        {isLoadingSaved && (
          <div className="py-8 flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
            <p className="text-sm text-gray-600 dark:text-gray-400">Checking for saved document...</p>
          </div>
        )}

        {/* Generation Options (before generating) */}
        {!hasResult && !isGenerating && !error && !isLoadingSaved && (
          <div className="space-y-4">
            {documentType === 'cover-letter' && (
              <div className="space-y-3">
                {/* Template Upload Toggle */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Use Custom Template
                  </span>
                  <button
                    onClick={() => setShowTemplateUpload(!showTemplateUpload)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <Upload className="w-4 h-4" />
                    {showTemplateUpload ? 'Hide' : 'Upload Template'}
                  </button>
                </div>

                {/* Template Upload Form */}
                {showTemplateUpload && (
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 space-y-2">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Paste a cover letter to use as a style reference. The AI will adapt this format while using your resume facts.
                    </p>
                    <textarea
                      value={templateContent}
                      onChange={(e) => setTemplateContent(e.target.value)}
                      placeholder="Paste your cover letter template here..."
                      className="w-full h-32 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={handleUploadTemplate}
                      disabled={!templateContent.trim() || uploadingTemplate}
                      className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {uploadingTemplate ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Save Template
                    </button>
                  </div>
                )}

                {/* Tone Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Tone
                  </label>
                  <div className="flex gap-2">
                    {(['professional', 'enthusiastic', 'formal'] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTone(t)}
                        className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                          tone === t
                            ? 'bg-blue-100 dark:bg-blue-900/40 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                            : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                        }`}
                      >
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Word Count */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Target Length: {maxWords} words
                  </label>
                  <input
                    type="range"
                    min="200"
                    max="600"
                    step="50"
                    value={maxWords}
                    onChange={(e) => setMaxWords(Number(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Brief (200)</span>
                    <span>Standard (400)</span>
                    <span>Detailed (600)</span>
                  </div>
                </div>
              </div>
            )}

            {documentType === 'resume' && (
              <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                <p>This will rewrite your resume sections to better match the job requirements:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Professional summary tailored to the role</li>
                  <li>Experience bullets emphasizing relevant skills</li>
                  <li>Skills reorganized by relevance</li>
                </ul>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  Contact info, dates, and job titles will remain unchanged.
                </p>
              </div>
            )}

            <button
              onClick={handleGenerate}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {documentType === 'resume' ? (
                <>
                  <FileText className="w-4 h-4" />
                  Generate Tailored Resume
                </>
              ) : (
                <>
                  <Mail className="w-4 h-4" />
                  Generate Cover Letter
                </>
              )}
            </button>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div className="py-12 flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
            <p className="text-gray-600 dark:text-gray-400">
              {documentType === 'resume'
                ? 'Analyzing job requirements and rewriting resume...'
                : 'Crafting your cover letter...'}
            </p>
            <p className="text-xs text-gray-500">This may take a minute</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  Generation Failed
                </p>
                <p className="text-sm text-red-700 dark:text-red-300 mt-1">{error}</p>
                <button
                  onClick={handleGenerate}
                  className="mt-3 text-sm text-red-700 dark:text-red-300 hover:underline"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {hasResult && (
          <div className="space-y-4">
            {/* Verification Status (for resume) */}
            {resumeResult?.verification && (
              <div
                className={`border rounded-lg p-3 ${getVerificationColor(
                  resumeResult.verification.status
                )}`}
              >
                <div className="flex items-center gap-2">
                  {getVerificationIcon(resumeResult.verification.status)}
                  <span className="font-medium text-gray-900 dark:text-white">
                    Verification: {resumeResult.verification.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 mt-1">
                  {resumeResult.verification.summary}
                </p>
              </div>
            )}

            {/* Keywords incorporated (for resume) */}
            {resumeResult?.rewritten_resume?.keywords_incorporated &&
              resumeResult.rewritten_resume.keywords_incorporated.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                    Keywords Incorporated
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {resumeResult.rewritten_resume.keywords_incorporated.map((keyword, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded-full"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            {/* Cover letter metadata */}
            {coverLetterResult?.cover_letter && (
              <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                <span>{coverLetterResult.cover_letter.word_count} words</span>
                <span>{coverLetterResult.cover_letter.paragraphs.length} paragraphs</span>
                {saved && (
                  <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                    <Check className="w-4 h-4" />
                    Saved
                  </span>
                )}
              </div>
            )}

            {/* View Toggle (resume only) */}
            {resumeResult?.rewritten_resume && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowChanges(false)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    !showChanges
                      ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  <FileOutput className="w-4 h-4" />
                  Final Resume
                </button>
                <button
                  onClick={() => setShowChanges(true)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    showChanges
                      ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  <GitCompare className="w-4 h-4" />
                  Show Changes
                </button>
              </div>
            )}

            {/* Document Content */}
            {(!resumeResult?.rewritten_resume || !showChanges) && (
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono leading-relaxed">
                  {plainText}
                </pre>
              </div>
            )}

            {/* Diff View */}
            {resumeResult?.rewritten_resume && showChanges && (
              <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                {/* Summary Changes */}
                {resumeResult.rewritten_resume.summary && (() => {
                  const summaryChanged = resumeResult.rewritten_resume.summary.original !== resumeResult.rewritten_resume.summary.rewritten;
                  const useOriginal = sectionSelections.summary === 'original';
                  const isRegenerating = regeneratingSection === 'summary';
                  return (
                    <div className={`border rounded-lg overflow-hidden ${useOriginal ? 'border-gray-300 dark:border-gray-600' : 'border-green-300 dark:border-green-700'}`}>
                      <div className="bg-gray-100 dark:bg-gray-800 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                        <span className="font-medium text-gray-900 dark:text-white text-sm">Summary</span>
                        <div className="flex items-center gap-2">
                          {isRegenerating ? (
                            <span className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Regenerating...
                            </span>
                          ) : (
                            <>
                              {!summaryChanged && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 italic">No changes</span>
                              )}
                              {summaryChanged && (
                                <button
                                  onClick={() => toggleSection('summary')}
                                  className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-colors ${
                                    useOriginal
                                      ? 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                                      : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                  }`}
                                  title={useOriginal ? 'Using original - click to use rewritten' : 'Using rewritten - click to use original'}
                                >
                                  {useOriginal ? <ToggleLeft className="w-4 h-4" /> : <ToggleRight className="w-4 h-4" />}
                                  {useOriginal ? 'Original' : 'Rewritten'}
                                </button>
                              )}
                              <button
                                onClick={() => openRegenerateModal('summary')}
                                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                                title="Regenerate with instructions"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Revise</span>
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {summaryChanged ? (
                        <div className="grid grid-cols-2 divide-x divide-gray-200 dark:divide-gray-700">
                          <div className={`p-3 ${!useOriginal ? 'bg-gray-50 dark:bg-gray-800/50 opacity-60' : 'bg-blue-50/50 dark:bg-blue-900/10 ring-2 ring-inset ring-blue-300 dark:ring-blue-700'}`}>
                            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Original</div>
                            <p className="text-sm text-gray-700 dark:text-gray-300">
                              {resumeResult.rewritten_resume.summary.original}
                            </p>
                          </div>
                          <div className={`p-3 ${useOriginal ? 'bg-gray-50 dark:bg-gray-800/50 opacity-60' : 'bg-green-50/50 dark:bg-green-900/10 ring-2 ring-inset ring-green-300 dark:ring-green-700'}`}>
                            <div className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">Rewritten</div>
                            <p className="text-sm text-gray-700 dark:text-gray-300">
                              {resumeResult.rewritten_resume.summary.rewritten}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <div className="p-3">
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            {resumeResult.rewritten_resume.summary.original}
                          </p>
                        </div>
                      )}
                      {resumeResult.rewritten_resume.summary.changes_made.length > 0 && (
                        <div className="px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border-t border-gray-200 dark:border-gray-700">
                          <span className="text-xs text-blue-700 dark:text-blue-300">
                            Changes: {resumeResult.rewritten_resume.summary.changes_made.join(' • ')}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Experience Changes */}
                {resumeResult.rewritten_resume.experience.map((exp, expIdx) => {
                  const hasAnyChanges = exp.original_bullets.some(
                    (original, idx) => original !== exp.rewritten_bullets[idx]
                  );
                  const isRegenerating = regeneratingSection === `experience-${expIdx}`;
                  // Check if any bullet in this experience uses rewritten (for border color)
                  const anyBulletRewritten = exp.original_bullets.some((_, bulletIdx) =>
                    sectionSelections[`experience-${expIdx}-bullet-${bulletIdx}`] === 'rewritten'
                  );
                  return (
                    <div key={expIdx} className={`border rounded-lg overflow-hidden ${!anyBulletRewritten ? 'border-gray-300 dark:border-gray-600' : 'border-green-300 dark:border-green-700'}`}>
                      <div className="bg-gray-100 dark:bg-gray-800 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                        <div>
                          <span className="font-medium text-gray-900 dark:text-white text-sm">
                            {exp.title} at {exp.company}
                          </span>
                          <span className="text-gray-500 dark:text-gray-400 text-xs ml-2">
                            {exp.start_date} - {exp.end_date}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {isRegenerating ? (
                            <span className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Regenerating...
                            </span>
                          ) : (
                            <>
                              {!hasAnyChanges && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 italic">No changes</span>
                              )}
                              <button
                                onClick={() => openRegenerateModal('experience', expIdx)}
                                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                                title="Regenerate with instructions"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Revise</span>
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="divide-y divide-gray-200 dark:divide-gray-700">
                        {exp.original_bullets.map((originalBullet, bulletIdx) => {
                          const rewrittenBullet = exp.rewritten_bullets[bulletIdx] || originalBullet;
                          const isChanged = originalBullet !== rewrittenBullet;
                          const bulletKey = `experience-${expIdx}-bullet-${bulletIdx}`;
                          const useOriginalBullet = sectionSelections[bulletKey] === 'original';

                          if (!isChanged) {
                            // Unchanged bullet - show single column without diff styling
                            return (
                              <div key={bulletIdx} className="p-2">
                                <span className="text-xs text-gray-400 dark:text-gray-500 mr-1">•</span>
                                <span className="text-sm text-gray-600 dark:text-gray-400">{originalBullet}</span>
                              </div>
                            );
                          }

                          // Changed bullet - show side-by-side diff with per-bullet toggle
                          return (
                            <div key={bulletIdx} className="relative">
                              <div className="grid grid-cols-2 divide-x divide-gray-200 dark:divide-gray-700">
                                <div
                                  className={`p-2 cursor-pointer transition-colors ${
                                    useOriginalBullet
                                      ? 'bg-blue-50/50 dark:bg-blue-900/10 ring-2 ring-inset ring-blue-300 dark:ring-blue-700'
                                      : 'bg-gray-50 dark:bg-gray-800/50 opacity-60 hover:opacity-80'
                                  }`}
                                  onClick={() => toggleSection(bulletKey)}
                                  title="Click to use original"
                                >
                                  <div className="flex items-start gap-1">
                                    <span className="text-xs text-gray-500 dark:text-gray-400 mr-1 flex-shrink-0">−</span>
                                    <span className="text-sm text-gray-700 dark:text-gray-300">{originalBullet}</span>
                                  </div>
                                  {useOriginalBullet && (
                                    <div className="absolute top-1 left-1">
                                      <Check className="w-3 h-3 text-blue-600 dark:text-blue-400" />
                                    </div>
                                  )}
                                </div>
                                <div
                                  className={`p-2 cursor-pointer transition-colors ${
                                    !useOriginalBullet
                                      ? 'bg-green-50/50 dark:bg-green-900/10 ring-2 ring-inset ring-green-300 dark:ring-green-700'
                                      : 'bg-gray-50 dark:bg-gray-800/50 opacity-60 hover:opacity-80'
                                  }`}
                                  onClick={() => toggleSection(bulletKey)}
                                  title="Click to use rewritten"
                                >
                                  <div className="flex items-start gap-1">
                                    <span className="text-xs text-green-500 dark:text-green-400 mr-1 flex-shrink-0">+</span>
                                    <span className="text-sm text-gray-700 dark:text-gray-300">{rewrittenBullet}</span>
                                  </div>
                                  {!useOriginalBullet && (
                                    <div className="absolute top-1 right-1">
                                      <Check className="w-3 h-3 text-green-600 dark:text-green-400" />
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {exp.bullet_changes.length > 0 && (
                        <div className="px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border-t border-gray-200 dark:border-gray-700">
                          <span className="text-xs text-blue-700 dark:text-blue-300">
                            {exp.bullet_changes.join(' • ')}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Skills Changes */}
                {resumeResult.rewritten_resume.skills && (() => {
                  const skills = resumeResult.rewritten_resume.skills;
                  const skillsReordered = skills.original_skills.some(
                    (skill, i) => skill !== skills.rewritten_skills[i]
                  );
                  const useOriginal = sectionSelections.skills === 'original';
                  const isRegenerating = regeneratingSection === 'skills';
                  return (
                    <div className={`border rounded-lg overflow-hidden ${useOriginal ? 'border-gray-300 dark:border-gray-600' : 'border-green-300 dark:border-green-700'}`}>
                      <div className="bg-gray-100 dark:bg-gray-800 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                        <span className="font-medium text-gray-900 dark:text-white text-sm">Skills</span>
                        <div className="flex items-center gap-2">
                          {isRegenerating ? (
                            <span className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Regenerating...
                            </span>
                          ) : (
                            <>
                              {!skillsReordered && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 italic">No changes</span>
                              )}
                              {skillsReordered && (
                                <button
                                  onClick={() => toggleSection('skills')}
                                  className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-colors ${
                                    useOriginal
                                      ? 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                                      : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                  }`}
                                  title={useOriginal ? 'Using original - click to use rewritten' : 'Using rewritten - click to use original'}
                                >
                                  {useOriginal ? <ToggleLeft className="w-4 h-4" /> : <ToggleRight className="w-4 h-4" />}
                                  {useOriginal ? 'Original' : 'Rewritten'}
                                </button>
                              )}
                              <button
                                onClick={() => openRegenerateModal('skills')}
                                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                                title="Regenerate with instructions"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                <span>Revise</span>
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {skillsReordered ? (
                        <div className="grid grid-cols-2 divide-x divide-gray-200 dark:divide-gray-700">
                          <div className={`p-3 ${!useOriginal ? 'bg-gray-50 dark:bg-gray-800/50 opacity-60' : 'bg-blue-50/50 dark:bg-blue-900/10'}`}>
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Original Order</div>
                            <div className="flex flex-wrap gap-1">
                              {skills.original_skills.map((skill, i) => (
                                <span key={i} className="px-2 py-0.5 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                                  {skill}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className={`p-3 ${useOriginal ? 'bg-gray-50 dark:bg-gray-800/50 opacity-60' : 'bg-green-50/50 dark:bg-green-900/10'}`}>
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Reordered (Relevant First)</div>
                            <div className="flex flex-wrap gap-1">
                              {skills.rewritten_skills.map((skill, i) => {
                                const isHighlighted = skills.skills_highlighted.includes(skill);
                                return (
                                  <span
                                    key={i}
                                    className={`px-2 py-0.5 text-xs rounded ${
                                      isHighlighted
                                        ? 'bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200 font-medium'
                                        : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                                    }`}
                                  >
                                    {skill}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="p-3">
                          <div className="flex flex-wrap gap-1">
                            {skills.original_skills.map((skill, i) => {
                              const isHighlighted = skills.skills_highlighted.includes(skill);
                              return (
                                <span
                                  key={i}
                                  className={`px-2 py-0.5 text-xs rounded ${
                                    isHighlighted
                                      ? 'bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200 font-medium'
                                      : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                                  }`}
                                >
                                  {skill}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="flex-1 py-2 px-4 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4 text-green-500" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy to Clipboard
                  </>
                )}
              </button>

              <button
                onClick={handleDownload}
                className="py-2 px-4 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </button>

              {documentType === 'cover-letter' && !saved && (
                <button
                  onClick={handleSaveCoverLetter}
                  disabled={saving}
                  className="py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  Save
                </button>
              )}
            </div>

            {/* Saved document info & Regenerate */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-gray-700">
              {savedDocument?.updated_at && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                  <Clock className="w-3.5 h-3.5" />
                  <span>
                    Saved {new Date(savedDocument.updated_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              )}
              <button
                onClick={handleRegenerate}
                className="flex items-center gap-1.5 py-1.5 px-3 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors ml-auto"
              >
                <RefreshCw className="w-4 h-4" />
                Regenerate All
              </button>
            </div>
          </div>
        )}

        {/* Regenerate Section Modal */}
        {showRegenerateModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <h3 className="font-medium text-gray-900 dark:text-white">
                    Regenerate Section
                  </h3>
                </div>
                <button
                  onClick={() => setShowRegenerateModal(null)}
                  className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Describe what you'd like to improve or change about this section:
                </p>
                <textarea
                  value={regenerateInstructions}
                  onChange={(e) => setRegenerateInstructions(e.target.value)}
                  placeholder="e.g., Make it more concise, emphasize leadership skills, add more quantifiable achievements..."
                  className="w-full h-24 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  autoFocus
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setShowRegenerateModal(null)}
                    className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      const parts = showRegenerateModal.split('-');
                      const sectionType = parts[0] as 'summary' | 'experience' | 'skills';
                      const sectionIndex = parts.length > 1 ? parseInt(parts[1], 10) : undefined;
                      handleRegenerateSection(sectionType, sectionIndex);
                    }}
                    disabled={!regenerateInstructions.trim()}
                    className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Regenerate
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
