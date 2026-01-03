import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import {
  ArrowLeft,
  ExternalLink,
  MapPin,
  Building2,
  Clock,
  Wifi,
  DollarSign,
  Star,
  CheckCircle,
  XCircle,
  AlertCircle,
  Upload,
} from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { Card, CardTitle } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { JobScoreBadge, JobScoreBar } from '../components/jobs/JobScoreBadge';
import { JobStatusDropdown } from '../components/jobs/JobStatusDropdown';
import { AttachmentList } from '../components/jobs/AttachmentList';
import { AttachmentUploadModal } from '../components/jobs/AttachmentUploadModal';
import { useJobStore } from '../store/jobStore';
import { useToast } from '../store/uiStore';
import { formatDistanceToNow } from 'date-fns';
import { ApplicationStatus } from '../types/job';

export function JobDetailPage() {
  const { jobUrl } = useParams<{ jobUrl: string }>();
  const decodedUrl = decodeURIComponent(jobUrl || '');
  const toast = useToast();
  const queryClient = useQueryClient();
  const { updateApplicationStatus } = useJobStore();
  const [showUploadModal, setShowUploadModal] = useState(false);

  const { data: job, isLoading, error } = useQuery({
    queryKey: ['job', decodedUrl],
    queryFn: () => jobsApi.getJob(decodedUrl),
    enabled: !!decodedUrl,
  });

  const handleStatusChange = async (status: ApplicationStatus) => {
    try {
      await updateApplicationStatus(decodedUrl, status);
      // Invalidate the query cache to refetch with updated status
      queryClient.invalidateQueries({ queryKey: ['job', decodedUrl] });
      toast.success(`Status updated to ${status.replace('_', ' ')}`);
    } catch {
      toast.error('Failed to update status');
    }
  };

  if (isLoading) {
    return <LoadingPage message="Loading job details..." />;
  }

  if (error || !job) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load job details
      </div>
    );
  }

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

    if (job.salary_min && job.salary_max) {
      return `${currency}${job.salary_min.toLocaleString()} - ${currency}${job.salary_max.toLocaleString()}${period}`;
    }
    if (job.salary_min) return `From ${currency}${job.salary_min.toLocaleString()}${period}`;
    return `Up to ${currency}${job.salary_max!.toLocaleString()}${period}`;
  };

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link
        to="/jobs"
        className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Jobs
      </Link>

      {/* Header */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main Info */}
        <div className="flex-1">
          <Card>
            <div className="flex gap-4">
              {job.company_logo_url ? (
                <img
                  src={job.company_logo_url}
                  alt={job.company}
                  className="w-16 h-16 rounded-lg object-contain bg-gray-50"
                />
              ) : (
                <div className="w-16 h-16 rounded-lg bg-gray-100 flex items-center justify-center">
                  <Building2 className="w-8 h-8 text-gray-400" />
                </div>
              )}
              <div className="flex-1">
                <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-lg text-gray-700">{job.company}</span>
                  {job.company_rating && (
                    <span className="flex items-center gap-1 text-yellow-600">
                      <Star className="w-4 h-4 fill-current" />
                      {job.company_rating.toFixed(1)}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-4 mt-3 text-gray-500">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-4 h-4" />
                    {job.location}
                  </span>
                  {job.remote && (
                    <span className="flex items-center gap-1 text-green-600">
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
                  {formatSalary() && (
                    <span className="flex items-center gap-1">
                      <DollarSign className="w-4 h-4" />
                      {formatSalary()}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 mt-6 pt-6 border-t">
              <JobStatusDropdown
                status={job.application_status || 'not_applied'}
                onChange={handleStatusChange}
              />
              <Button
                onClick={() => window.open(job.job_url, '_blank')}
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                View Original
              </Button>
            </div>
          </Card>
        </div>

        {/* Score Card */}
        <div className="lg:w-80">
          <Card>
            <CardTitle>Match Score</CardTitle>
            <div className="mt-4 text-center">
              <JobScoreBadge score={job.match_score} size="lg" />
              <div className="mt-4">
                <JobScoreBar score={job.match_score} />
              </div>
            </div>
            {job.match_explanation && (
              <p className="mt-4 text-sm text-gray-600">{job.match_explanation}</p>
            )}
          </Card>
        </div>
      </div>

      {/* Gap Analysis & Suggestions */}
      {(job.gap_analysis || job.resume_suggestions) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {job.gap_analysis && (
            <Card>
              <CardTitle>Gap Analysis</CardTitle>
              <div className="mt-4 space-y-4 text-sm">
                <div className="prose prose-sm max-w-none text-gray-600">
                  {job.gap_analysis.split('\n').map((line, i) => (
                    <p key={i} className="flex items-start gap-2">
                      {line.includes('Strength') || line.includes('+') ? (
                        <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                      ) : line.includes('Gap') || line.includes('-') ? (
                        <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                      )}
                      {line}
                    </p>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {job.resume_suggestions && (
            <Card>
              <CardTitle>Resume Suggestions</CardTitle>
              <div className="mt-4 text-sm text-gray-600 whitespace-pre-wrap">
                {job.resume_suggestions}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Application Documents */}
      <Card>
        <div className="flex items-center justify-between">
          <CardTitle>Application Documents</CardTitle>
          <Button size="sm" onClick={() => setShowUploadModal(true)}>
            <Upload className="w-4 h-4 mr-2" />
            Upload
          </Button>
        </div>
        <div className="mt-4">
          <AttachmentList jobUrl={decodedUrl} />
        </div>
      </Card>

      <AttachmentUploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        jobUrl={decodedUrl}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['attachments', decodedUrl] });
          toast.success('Attachment uploaded successfully');
        }}
      />

      {/* Skills & Requirements */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {job.skills && job.skills.length > 0 && (
          <Card>
            <CardTitle>Skills</CardTitle>
            <div className="flex flex-wrap gap-2 mt-4">
              {job.skills.map((skill, i) => (
                <Badge key={i} variant="info">
                  {skill}
                </Badge>
              ))}
            </div>
          </Card>
        )}

        {job.requirements && job.requirements.length > 0 && (
          <Card>
            <CardTitle>Requirements</CardTitle>
            <ul className="mt-4 space-y-2">
              {job.requirements.map((req, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                  <span className="text-gray-400">•</span>
                  {req}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Benefits */}
      {job.benefits && job.benefits.length > 0 && (
        <Card>
          <CardTitle>Benefits</CardTitle>
          <div className="flex flex-wrap gap-2 mt-4">
            {job.benefits.map((benefit, i) => (
              <Badge key={i} variant="success">
                {benefit}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      {/* Description */}
      {job.description && (
        <Card>
          <CardTitle>Job Description</CardTitle>
          <div className="mt-4 prose prose-sm max-w-none text-gray-600">
            <ReactMarkdown>{job.description}</ReactMarkdown>
          </div>
        </Card>
      )}
    </div>
  );
}
