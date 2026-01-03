export interface Job {
  job_url: string;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  source: 'indeed' | 'glassdoor' | string;
  description?: string;
  job_type?: string;
  date_posted?: string;

  // Salary
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  salary_period?: string;

  // Matching
  match_score?: number;
  match_explanation?: string;
  gap_analysis?: string;
  resume_suggestions?: string;
  is_relevant?: boolean;

  // Skills & Requirements
  skills?: string[];
  requirements?: string[];
  benefits?: string[];
  work_arrangements?: string[];

  // Company info
  company_url?: string;
  company_industry?: string;
  company_size?: string;
  company_description?: string;
  company_rating?: number;
  company_logo_url?: string;

  // Location
  location_city?: string;
  location_state?: string;
  location_country_code?: string;

  // Timestamps
  first_seen: string;
  last_seen: string;

  // Application status (joined from job_applications)
  application_status?: ApplicationStatus;
  applied_at?: string;
  application_notes?: string;
}

export type ApplicationStatus =
  | 'not_applied'
  | 'applied'
  | 'phone_screen'
  | 'interviewing'
  | 'final_round'
  | 'offer'
  | 'rejected'
  | 'withdrawn'
  | 'no_response';

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  not_applied: 'Not Applied',
  applied: 'Applied',
  phone_screen: 'Phone Screen',
  interviewing: 'Interviewing',
  final_round: 'Final Round',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
  no_response: 'No Response',
};

export const APPLICATION_STATUS_COLORS: Record<ApplicationStatus, string> = {
  not_applied: 'bg-gray-100 text-gray-700',
  applied: 'bg-blue-100 text-blue-700',
  phone_screen: 'bg-purple-100 text-purple-700',
  interviewing: 'bg-yellow-100 text-yellow-700',
  final_round: 'bg-orange-100 text-orange-700',
  offer: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  withdrawn: 'bg-gray-100 text-gray-500',
  no_response: 'bg-gray-100 text-gray-500',
};

export interface JobFilters {
  source?: string | null;
  min_score?: number | null;
  max_score?: number | null;
  remote?: boolean | null;
  location?: string | null;
  company?: string | null;
  status?: ApplicationStatus | null;
  search?: string | null;
  sort_by: 'date_posted' | 'match_score' | 'first_seen' | 'company' | 'title';
  sort_order: 'asc' | 'desc';
}

export interface JobStats {
  total_jobs: number;
  scored_jobs: number;
  unscored_jobs: number;
  avg_score: number;
  high_matches: number;
  medium_matches: number;
  low_matches: number;
  by_source: Record<string, number>;
  thresholds: {
    excellent: number;
    good: number;
    fair: number;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Attachment types
export type AttachmentType = 'resume' | 'cover_letter';

export interface JobAttachment {
  id: string;
  job_url: string;
  attachment_type: AttachmentType;
  filename: string;
  file_extension: string;
  file_size: number;
  file_size_display: string;
  mime_type: string;
  notes?: string;
  created_at: string;
}

export const ATTACHMENT_TYPE_LABELS: Record<AttachmentType, string> = {
  resume: 'Resume',
  cover_letter: 'Cover Letter',
};

export const ATTACHMENT_TYPE_COLORS: Record<AttachmentType, string> = {
  resume: 'bg-blue-100 text-blue-700',
  cover_letter: 'bg-purple-100 text-purple-700',
};
