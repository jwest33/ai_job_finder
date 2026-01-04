import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  MapPin,
  Building2,
  Clock,
  ExternalLink,
  Wifi,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Sparkles,
  FileText,
  Target,
} from 'lucide-react';
import {
  Job,
  ApplicationStatus,
  parseGapAnalysis,
  parseResumeSuggestions,
} from '../../types/job';
import { JobScoreBadge } from './JobScoreBadge';
import { JobStatusDropdown } from './JobStatusDropdown';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { formatDistanceToNow } from 'date-fns';

interface JobCardProps {
  job: Job;
  onStatusChange?: (jobUrl: string, status: ApplicationStatus) => void;
}

export function JobCard({ job, onStatusChange }: JobCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const gapAnalysis = parseGapAnalysis(job.gap_analysis);
  const resumeSuggestions = parseResumeSuggestions(job.resume_suggestions);
  const hasAnalysis = gapAnalysis || resumeSuggestions;

  const sourceColors: Record<string, string> = {
    indeed: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
    glassdoor: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
  };

  const formatSalary = () => {
    if (!job.salary_min && !job.salary_max) return null;

    // Use $ symbol, or currency code with space
    const rawCurrency = job.salary_currency || 'USD';
    const currency = rawCurrency === 'USD' ? '$' : `${rawCurrency} `;

    // Abbreviate period
    const period = job.salary_period === 'yearly' ? '/yr' :
                   job.salary_period === 'monthly' ? '/mo' :
                   job.salary_period === 'hourly' ? '/hr' :
                   job.salary_period ? `/${job.salary_period}` : '/yr';

    const formatAmount = (amount: number) => {
      if (amount >= 1000) {
        return `${(amount / 1000).toFixed(0)}k`;
      }
      return amount.toFixed(0);
    };

    if (job.salary_min && job.salary_max) {
      return `${currency}${formatAmount(job.salary_min)} - ${currency}${formatAmount(job.salary_max)}${period}`;
    }
    if (job.salary_min) {
      return `From ${currency}${formatAmount(job.salary_min)}${period}`;
    }
    return `Up to ${currency}${formatAmount(job.salary_max!)}${period}`;
  };

  const salary = formatSalary();
  const encodedUrl = encodeURIComponent(job.job_url);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex gap-4">
        {/* Company Logo */}
        <div className="flex-shrink-0">
          {job.company_logo_url ? (
            <img
              src={job.company_logo_url}
              alt={job.company}
              className="w-12 h-12 rounded-lg object-contain bg-gray-50 dark:bg-gray-700"
            />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
              <Building2 className="w-6 h-6 text-gray-400" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <Link
                to={`/jobs/${encodedUrl}`}
                className="text-lg font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors line-clamp-1"
              >
                {job.title}
              </Link>
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                <span className="font-medium">{job.company}</span>
                {job.company_rating && (
                  <span className="text-yellow-600 dark:text-yellow-500">★ {job.company_rating.toFixed(1)}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <JobScoreBadge score={job.match_score} />
            </div>
          </div>

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              {job.location}
            </span>
            {job.remote && (
              <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                <Wifi className="w-4 h-4" />
                Remote
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {job.date_posted
                ? `Posted ${formatDistanceToNow(new Date(job.date_posted), { addSuffix: false })} ago`
                : `Added ${formatDistanceToNow(new Date(job.first_seen), { addSuffix: false })} ago`
              }
            </span>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <Badge className={sourceColors[job.source] || 'bg-gray-100 text-gray-700'}>
              {job.source}
            </Badge>
            {job.job_type && <Badge variant="outline">{job.job_type}</Badge>}
            {salary && <Badge variant="outline">{salary}</Badge>}
          </div>

          {/* Analysis Summary Indicators */}
          {hasAnalysis && !isExpanded && (
            <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-gray-500 dark:text-gray-400">
              {gapAnalysis && (
                <>
                  {gapAnalysis.strengths.length > 0 && (
                    <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                      <CheckCircle className="w-3 h-3" />
                      {gapAnalysis.strengths.length} strengths
                    </span>
                  )}
                  {gapAnalysis.gaps.length > 0 && (
                    <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                      <Target className="w-3 h-3" />
                      {gapAnalysis.gaps.length} gaps
                    </span>
                  )}
                  {gapAnalysis.red_flags.length > 0 && (
                    <span className="flex items-center gap-1 text-red-600 dark:text-red-400">
                      <AlertTriangle className="w-3 h-3" />
                      {gapAnalysis.red_flags.length} flags
                    </span>
                  )}
                </>
              )}
              {resumeSuggestions && resumeSuggestions.keywords.length > 0 && (
                <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                  <Sparkles className="w-3 h-3" />
                  {resumeSuggestions.keywords.length} keywords
                </span>
              )}
            </div>
          )}

          {/* Expanded Analysis Section */}
          {hasAnalysis && isExpanded && (
            <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 space-y-4">
              {/* Gap Analysis */}
              {gapAnalysis && (
                <div className="space-y-3">
                  {/* Assessment */}
                  {gapAnalysis.assessment && (
                    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {gapAnalysis.assessment}
                      </p>
                    </div>
                  )}

                  {/* Strengths */}
                  {gapAnalysis.strengths.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-green-700 dark:text-green-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Strengths
                      </h4>
                      <ul className="space-y-1">
                        {gapAnalysis.strengths.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                            <span className="text-green-500 mt-1">+</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Gaps */}
                  {gapAnalysis.gaps.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-amber-700 dark:text-amber-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                        <Target className="w-3 h-3" />
                        Gaps to Address
                      </h4>
                      <ul className="space-y-1">
                        {gapAnalysis.gaps.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                            <span className="text-amber-500 mt-1">-</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Red Flags */}
                  {gapAnalysis.red_flags.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-red-700 dark:text-red-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Red Flags
                      </h4>
                      <ul className="space-y-1">
                        {gapAnalysis.red_flags.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                            <XCircle className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Resume Suggestions */}
              {resumeSuggestions && (
                <div className="space-y-3">
                  {/* Resume Summary */}
                  {resumeSuggestions.resume_summary && (
                    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                      <h4 className="text-xs font-medium text-blue-700 dark:text-blue-400 uppercase tracking-wide mb-1 flex items-center gap-1">
                        <FileText className="w-3 h-3" />
                        Suggested Resume Summary
                      </h4>
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        {resumeSuggestions.resume_summary}
                      </p>
                    </div>
                  )}

                  {/* Keywords */}
                  {resumeSuggestions.keywords.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-blue-700 dark:text-blue-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Keywords to Include
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {resumeSuggestions.keywords.map((keyword, i) => (
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

                  {/* Experience Highlights */}
                  {resumeSuggestions.experience_highlights.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-purple-700 dark:text-purple-400 uppercase tracking-wide mb-2">
                        Experience to Highlight
                      </h4>
                      <ul className="space-y-1">
                        {resumeSuggestions.experience_highlights.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                            <span className="text-purple-500 mt-1">•</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Cover Letter Points */}
                  {resumeSuggestions.cover_letter_points.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-indigo-700 dark:text-indigo-400 uppercase tracking-wide mb-2">
                        Cover Letter Points
                      </h4>
                      <ul className="space-y-1">
                        {resumeSuggestions.cover_letter_points.map((item, i) => (
                          <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                            <span className="text-indigo-500 mt-1">•</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <JobStatusDropdown
                status={job.application_status || 'not_applied'}
                onChange={(status) => onStatusChange?.(job.job_url, status)}
              />
              {hasAnalysis && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                >
                  {isExpanded ? (
                    <>
                      <ChevronUp className="w-4 h-4" />
                      Hide Analysis
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-4 h-4" />
                      Show Analysis
                    </>
                  )}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
              >
                <ExternalLink className="w-4 h-4" />
                View Original
              </a>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
