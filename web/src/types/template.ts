export interface ResumeContent {
  content: string;
  last_modified?: string;
}

export interface RequirementsContent {
  content: string;
  data?: RequirementsData;
  last_modified?: string;
}

export interface RequirementsData {
  candidate_profile?: {
    self_description?: string;
    key_strengths?: string[];
    technical_skills?: string[];
    career_goals?: string;
    must_haves?: string[];
    avoid_list?: string[];
  };
  job_requirements?: {
    target_roles?: string[];
    search_terms?: string[];
    required_skills?: string[];
    preferred_skills?: string[];
  };
  preferences?: {
    remote_preference?: string;
    salary_range?: {
      min?: number;
      max?: number;
    };
    locations?: string[];
  };
}

export interface TemplateValidation {
  resume: {
    valid: boolean;
    exists: boolean;
    size?: number;
    errors?: string[];
  };
  requirements: {
    valid: boolean;
    exists: boolean;
    size?: number;
    errors?: string[];
  };
}

export interface ATSCategoryResult {
  score: number;
  issues: string[];
  recommendations: string[];
}

export interface ATSScoreResult {
  overall_score: number;
  categories: {
    keywords: ATSCategoryResult;
    formatting: ATSCategoryResult;
    sections: ATSCategoryResult;
    achievements: ATSCategoryResult;
    contact_info: ATSCategoryResult;
    skills: ATSCategoryResult;
  };
  summary: string;
  top_recommendations: string[];
}

export interface ResumeUploadResponse {
  success: boolean;
  content: string;
  message: string;
}

// Parsed resume types (from AI parser)
export interface ContactInfo {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  website: string;
}

export interface ExperienceEntry {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  location: string;
  bullets: string[];
}

export interface EducationEntry {
  degree: string;
  school: string;
  year: string;
  gpa: string;
  honors: string;
}

export interface ParsedResume {
  contact: ContactInfo;
  summary: string;
  experience: ExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  certifications: string[];
  languages: string[];
}
