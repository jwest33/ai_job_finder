import { useState } from 'react';
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
} from 'lucide-react';
import { Modal } from '../common/Modal';
import { documentsApi } from '../../api/documents';
import type { Job } from '../../types/job';
import type {
  ResumeRewriteResponse,
  CoverLetterResponse,
  VerificationStatus,
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

  // Cover letter options
  const [tone, setTone] = useState<'professional' | 'enthusiastic' | 'formal'>('professional');
  const [maxWords, setMaxWords] = useState(400);

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
    const text = documentType === 'resume'
      ? resumeResult?.plain_text
      : coverLetterResult?.plain_text;

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
    const text = documentType === 'resume'
      ? resumeResult?.plain_text
      : coverLetterResult?.plain_text;

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
    onClose();
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

        {/* Generation Options (before generating) */}
        {!hasResult && !isGenerating && !error && (
          <div className="space-y-4">
            {documentType === 'cover-letter' && (
              <div className="space-y-3">
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

            {/* Document Content */}
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
              <pre className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono leading-relaxed">
                {plainText}
              </pre>
            </div>

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

            {/* Generate another */}
            <button
              onClick={handleGenerate}
              className="w-full py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            >
              Regenerate
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
