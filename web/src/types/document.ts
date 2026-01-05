/**
 * Types for resume rewriting and cover letter generation.
 * Matches the Pydantic models in src/job_matcher/models/resume_rewrite.py
 */

// =============================================================================
// Contact & Experience Types (from resume parser)
// =============================================================================

export interface ContactInfo {
  name: string;
  email: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  portfolio?: string;
}

export interface EducationEntry {
  degree: string;
  school: string;
  year?: string;
  gpa?: string;
  honors?: string;
}

// =============================================================================
// Rewritten Section Types
// =============================================================================

export interface RewrittenSummary {
  original: string;
  rewritten: string;
  keywords_added: string[];
  changes_made: string[];
}

export interface RewrittenExperienceEntry {
  // Immutable fields
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  location: string;
  // Mutable fields
  original_bullets: string[];
  rewritten_bullets: string[];
  bullet_changes: string[];
}

export interface RewrittenSkills {
  original_skills: string[];
  rewritten_skills: string[];
  skills_highlighted: string[];
  organization_strategy: string;
}

export interface RewrittenResume {
  contact: ContactInfo;
  summary: RewrittenSummary;
  experience: RewrittenExperienceEntry[];
  skills: RewrittenSkills;
  education: EducationEntry[];
  certifications: string[];
  languages: string[];
  target_job_title: string;
  target_company: string;
  keywords_incorporated: string[];
  overall_changes: string[];
}

// =============================================================================
// Verification Types
// =============================================================================

export type VerificationStatus = 'passed' | 'warning' | 'failed';

export interface FactDiscrepancy {
  section: string;
  field: string;
  original_value: string;
  rewritten_value: string;
  discrepancy_type: 'missing' | 'modified' | 'fabricated';
  severity: 'critical' | 'warning' | 'info';
}

export interface SchemaVerificationResult {
  passed: boolean;
  discrepancies: FactDiscrepancy[];
  checks_performed: Record<string, boolean>;
}

export interface LLMVerificationResult {
  passed: boolean;
  confidence: number;
  findings: string[];
  potential_issues: string[];
  recommendation: string;
}

export interface VerificationReport {
  status: VerificationStatus;
  schema_check: SchemaVerificationResult;
  llm_check: LLMVerificationResult;
  overall_passed: boolean;
  summary: string;
}

// =============================================================================
// Cover Letter Types
// =============================================================================

export interface CoverLetterParagraph {
  type: 'opening' | 'body' | 'skills' | 'closing';
  content: string;
  facts_used: string[];
}

export interface CoverLetter {
  greeting: string;
  paragraphs: CoverLetterParagraph[];
  closing: string;
  signature: string;
  target_job_title: string;
  target_company: string;
  word_count: number;
  facts_from_resume: string[];
  job_requirements_addressed: string[];
}

// =============================================================================
// API Request/Response Types
// =============================================================================

export interface ResumeRewriteRequest {
  job_url: string;
  sections_to_rewrite?: string[];
}

export interface ResumeRewriteResponse {
  success: boolean;
  rewritten_resume?: RewrittenResume;
  verification?: VerificationReport;
  plain_text?: string;
  error?: string;
}

export interface CoverLetterRequest {
  job_url: string;
  tone?: 'professional' | 'enthusiastic' | 'formal';
  max_words?: number;
}

export interface CoverLetterResponse {
  success: boolean;
  cover_letter?: CoverLetter;
  plain_text?: string;
  error?: string;
}

export interface SavedCoverLetter {
  found: boolean;
  content?: string;
  updated_at?: string;
}
