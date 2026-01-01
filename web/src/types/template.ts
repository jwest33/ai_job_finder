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
