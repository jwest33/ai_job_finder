import { Link } from 'react-router-dom';
import { MapPin, Building2, Clock, ExternalLink, Wifi } from 'lucide-react';
import { Job, ApplicationStatus } from '../../types/job';
import { JobScoreBadge } from './JobScoreBadge';
import { JobStatusDropdown } from './JobStatusDropdown';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface JobCardProps {
  job: Job;
  onStatusChange?: (jobUrl: string, status: ApplicationStatus) => void;
}

export function JobCard({ job, onStatusChange }: JobCardProps) {
  const sourceColors: Record<string, string> = {
    indeed: 'bg-blue-100 text-blue-700',
    glassdoor: 'bg-green-100 text-green-700',
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
              className="w-12 h-12 rounded-lg object-contain bg-gray-50"
            />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-gray-100 flex items-center justify-center">
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
                className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors line-clamp-1"
              >
                {job.title}
              </Link>
              <div className="flex items-center gap-2 text-sm text-gray-600 mt-0.5">
                <span className="font-medium">{job.company}</span>
                {job.company_rating && (
                  <span className="text-yellow-600">★ {job.company_rating.toFixed(1)}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <JobScoreBadge score={job.match_score} />
            </div>
          </div>

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-gray-500">
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
          </div>

          {/* Tags */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <Badge className={sourceColors[job.source] || 'bg-gray-100 text-gray-700'}>
              {job.source}
            </Badge>
            {job.job_type && <Badge variant="outline">{job.job_type}</Badge>}
            {salary && <Badge variant="outline">{salary}</Badge>}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
            <JobStatusDropdown
              status={job.application_status || 'not_applied'}
              onChange={(status) => onStatusChange?.(job.job_url, status)}
            />
            <div className="flex items-center gap-2">
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
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
