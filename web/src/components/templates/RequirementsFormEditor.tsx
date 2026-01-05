import { useState, useEffect, useRef } from 'react';
import { TagInput } from '../common/TagInput';
import yaml from 'js-yaml';

interface RequirementsFormData {
  // Candidate profile fields
  selfDescription: string;
  keyStrengths: string[];
  technicalSkills: string[];

  // Job requirements fields
  targetRoles: string[];
  relatedKeywords: string[];
  titleExcludeKeywords: string[];
  searchJobs: string[];
  experienceMin: string;
  experienceMax: string;
  preferredSkills: string[];
  careerGoals: string;
  mustHaves: string[];
  avoidList: string[];
  companySizes: string[];

  // Preferences fields
  remoteOnly: boolean;
  salaryMin: string;
  salaryMax: string;
  salaryPeriod: string;
  locations: string[];
  jobTypes: string[];
  maxJobAgeDays: string;
}

interface RequirementsFormEditorProps {
  content: string;
  onChange: (content: string) => void;
}

const SALARY_PERIOD_OPTIONS = [
  { value: 'yearly', label: 'Yearly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'hourly', label: 'Hourly' },
];

const COMPANY_SIZE_OPTIONS = [
  { value: 'startup', label: 'Startup (1-50)' },
  { value: 'small', label: 'Small (51-200)' },
  { value: 'medium', label: 'Medium (201-1000)' },
  { value: 'large', label: 'Large (1001-10000)' },
  { value: 'enterprise', label: 'Enterprise (10000+)' },
];

const JOB_TYPE_OPTIONS = [
  { value: 'full-time', label: 'Full-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'part-time', label: 'Part-time' },
];

// Parse YAML content to form data
function parseRequirements(content: string): RequirementsFormData {
  const defaults: RequirementsFormData = {
    selfDescription: '',
    keyStrengths: [],
    technicalSkills: [],
    targetRoles: [],
    relatedKeywords: [],
    titleExcludeKeywords: [],
    searchJobs: [],
    experienceMin: '',
    experienceMax: '',
    preferredSkills: [],
    careerGoals: '',
    mustHaves: [],
    avoidList: [],
    companySizes: [],
    remoteOnly: false,
    salaryMin: '',
    salaryMax: '',
    salaryPeriod: 'yearly',
    locations: [],
    jobTypes: ['full-time'],
    maxJobAgeDays: ''
  };

  try {
    const data = yaml.load(content) as Record<string, unknown>;
    if (!data || typeof data !== 'object') return defaults;

    const profile = (data.candidate_profile || {}) as Record<string, unknown>;
    const requirements = (data.job_requirements || {}) as Record<string, unknown>;
    const preferences = (data.preferences || {}) as Record<string, unknown>;
    const experience = (requirements.experience || {}) as Record<string, unknown>;
    const skills = (requirements.skills || {}) as Record<string, unknown>;

    return {
      // Candidate profile
      selfDescription: String(profile.self_description || ''),
      keyStrengths: Array.isArray(profile.key_strengths) ? profile.key_strengths : [],
      technicalSkills: Array.isArray(profile.technical_skills) ? profile.technical_skills : [],

      // Job requirements
      targetRoles: Array.isArray(requirements.target_roles) ? requirements.target_roles : [],
      relatedKeywords: Array.isArray(requirements.related_keywords) ? requirements.related_keywords : [],
      titleExcludeKeywords: Array.isArray(requirements.title_exclude_keywords) ? requirements.title_exclude_keywords : [],
      searchJobs: Array.isArray(requirements.search_jobs) ? requirements.search_jobs : [],
      experienceMin: experience.years_min !== undefined ? String(experience.years_min) : '',
      experienceMax: experience.years_max !== undefined ? String(experience.years_max) : '',
      preferredSkills: Array.isArray(skills.preferred) ? skills.preferred : [],
      careerGoals: String(requirements.career_goals || ''),
      mustHaves: Array.isArray(requirements.must_haves) ? requirements.must_haves : [],
      avoidList: Array.isArray(requirements.avoid) ? requirements.avoid : [],
      companySizes: Array.isArray(requirements.company_sizes) ? requirements.company_sizes : [],

      // Preferences
      remoteOnly: Boolean(preferences.remote_only),
      salaryMin: preferences.min_salary !== undefined ? String(preferences.min_salary) : '',
      salaryMax: preferences.max_salary !== undefined ? String(preferences.max_salary) : '',
      salaryPeriod: String(preferences.salary_period || 'yearly'),
      locations: Array.isArray(preferences.locations) ? preferences.locations : [],
      jobTypes: Array.isArray(preferences.job_types) ? preferences.job_types : ['full-time'],
      maxJobAgeDays: preferences.max_job_age_days !== undefined ? String(preferences.max_job_age_days) : ''
    };
  } catch {
    return defaults;
  }
}

// Serialize form data to YAML
function serializeRequirements(data: RequirementsFormData): string {
  const output: Record<string, unknown> = {};

  // Job Requirements (comes first in the YAML structure)
  const jobRequirements: Record<string, unknown> = {};
  if (data.targetRoles.length) jobRequirements.target_roles = data.targetRoles;
  if (data.relatedKeywords.length) jobRequirements.related_keywords = data.relatedKeywords;
  if (data.titleExcludeKeywords.length) jobRequirements.title_exclude_keywords = data.titleExcludeKeywords;
  if (data.searchJobs.length) jobRequirements.search_jobs = data.searchJobs;

  const expMin = parseInt(data.experienceMin);
  const expMax = parseInt(data.experienceMax);
  if (!isNaN(expMin) || !isNaN(expMax)) {
    const experience: Record<string, number> = {};
    if (!isNaN(expMin)) experience.years_min = expMin;
    if (!isNaN(expMax)) experience.years_max = expMax;
    jobRequirements.experience = experience;
  }

  if (data.preferredSkills.length) {
    jobRequirements.skills = { preferred: data.preferredSkills };
  }

  if (data.careerGoals) jobRequirements.career_goals = data.careerGoals;
  if (data.mustHaves.length) jobRequirements.must_haves = data.mustHaves;
  if (data.avoidList.length) jobRequirements.avoid = data.avoidList;
  if (data.companySizes.length) jobRequirements.company_sizes = data.companySizes;

  if (Object.keys(jobRequirements).length) {
    output.job_requirements = jobRequirements;
  }

  // Preferences
  const preferences: Record<string, unknown> = {};
  preferences.remote_only = data.remoteOnly;

  const salaryMin = parseInt(data.salaryMin);
  const salaryMax = parseInt(data.salaryMax);
  if (!isNaN(salaryMin)) preferences.min_salary = salaryMin;
  if (!isNaN(salaryMax)) preferences.max_salary = salaryMax;
  if (data.salaryPeriod) preferences.salary_period = data.salaryPeriod;

  if (data.locations.length) preferences.locations = data.locations;
  if (data.jobTypes.length) preferences.job_types = data.jobTypes;

  const maxAge = parseInt(data.maxJobAgeDays);
  if (!isNaN(maxAge)) preferences.max_job_age_days = maxAge;

  if (Object.keys(preferences).length) {
    output.preferences = preferences;
  }

  // Candidate Profile (optional, at end)
  const candidateProfile: Record<string, unknown> = {};
  if (data.selfDescription) candidateProfile.self_description = data.selfDescription;
  if (data.keyStrengths.length) candidateProfile.key_strengths = data.keyStrengths;
  if (data.technicalSkills.length) candidateProfile.technical_skills = data.technicalSkills;

  if (Object.keys(candidateProfile).length) {
    output.candidate_profile = candidateProfile;
  }

  return yaml.dump(output, { indent: 2, lineWidth: -1 });
}

// Form Section Component
function FormSection({ title, description, children }: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="bg-gray-50 dark:bg-gray-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h3>
        {description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>}
      </div>
      <div className="p-4 space-y-4 bg-white dark:bg-gray-800">
        {children}
      </div>
    </div>
  );
}

export function RequirementsFormEditor({ content, onChange }: RequirementsFormEditorProps) {
  const [formData, setFormData] = useState<RequirementsFormData>(() => parseRequirements(content));
  const isInitialMount = useRef(true);

  // Update parent when form data changes (skip initial mount)
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    const serialized = serializeRequirements(formData);
    onChange(serialized);
  }, [formData]);

  // Re-parse if content changes externally
  useEffect(() => {
    const currentSerialized = serializeRequirements(formData);
    if (content !== currentSerialized) {
      setFormData(parseRequirements(content));
    }
  }, [content]);

  const updateField = <K extends keyof RequirementsFormData>(
    field: K,
    value: RequirementsFormData[K]
  ) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const toggleArrayItem = (field: 'companySizes' | 'jobTypes', value: string) => {
    setFormData(prev => {
      const current = prev[field];
      if (current.includes(value)) {
        return { ...prev, [field]: current.filter(v => v !== value) };
      } else {
        return { ...prev, [field]: [...current, value] };
      }
    });
  };

  return (
    <div className="space-y-4 p-4 h-full overflow-y-auto bg-white dark:bg-gray-800">
      {/* Target Roles & Search */}
      <FormSection
        title="Target Roles"
        description="Job titles to search for and match against"
      >
        <TagInput
          label="Target Role Titles"
          value={formData.targetRoles}
          onChange={(v) => updateField('targetRoles', v)}
          placeholder="Senior Data Engineer, Staff Engineer..."
        />

        <TagInput
          label="Search Jobs (exact search terms)"
          value={formData.searchJobs}
          onChange={(v) => updateField('searchJobs', v)}
          placeholder="Terms used by the scraper..."
        />

        <TagInput
          label="Related Keywords"
          value={formData.relatedKeywords}
          onChange={(v) => updateField('relatedKeywords', v)}
          placeholder="data pipeline, ETL, Snowflake..."
        />

        <TagInput
          label="Title Exclude Keywords"
          value={formData.titleExcludeKeywords}
          onChange={(v) => updateField('titleExcludeKeywords', v)}
          placeholder="junior, intern, entry level..."
        />
      </FormSection>

      {/* Experience & Skills */}
      <FormSection
        title="Experience & Skills"
        description="Your experience level and preferred skills"
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Experience Range (Years)
            </label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                value={formData.experienceMin}
                onChange={(e) => updateField('experienceMin', e.target.value)}
                placeholder="Min"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <span className="text-gray-500 dark:text-gray-400">-</span>
              <input
                type="number"
                value={formData.experienceMax}
                onChange={(e) => updateField('experienceMax', e.target.value)}
                placeholder="Max"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </div>
        </div>

        <TagInput
          label="Preferred Skills"
          value={formData.preferredSkills}
          onChange={(v) => updateField('preferredSkills', v)}
          placeholder="Snowflake, dbt, Airflow..."
        />
      </FormSection>

      {/* Career Goals */}
      <FormSection
        title="Career Goals"
        description="What you're looking for in your next role"
      >
        <textarea
          value={formData.careerGoals}
          onChange={(e) => updateField('careerGoals', e.target.value)}
          placeholder="Describe what you're seeking in your next role, technologies you want to work with, and your career objectives..."
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[100px]"
        />
      </FormSection>

      {/* Must Haves / Avoid */}
      <FormSection
        title="Deal Breakers"
        description="Non-negotiable requirements and red flags"
      >
        <TagInput
          label="Must Haves"
          value={formData.mustHaves}
          onChange={(v) => updateField('mustHaves', v)}
          placeholder="Remote role, Modern tech stack..."
        />

        <TagInput
          label="Avoid List"
          value={formData.avoidList}
          onChange={(v) => updateField('avoidList', v)}
          placeholder="Contract positions, Entry-level roles..."
        />
      </FormSection>

      {/* Preferences */}
      <FormSection
        title="Job Preferences"
        description="Work arrangement and compensation preferences"
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={formData.remoteOnly}
                onChange={(e) => updateField('remoteOnly', e.target.checked)}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
              />
              Remote Only
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Job Age (Days)
            </label>
            <input
              type="number"
              value={formData.maxJobAgeDays}
              onChange={(e) => updateField('maxJobAgeDays', e.target.value)}
              placeholder="21"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Min Salary
            </label>
            <div className="flex gap-1 items-center">
              <span className="text-gray-500 dark:text-gray-400">$</span>
              <input
                type="number"
                value={formData.salaryMin}
                onChange={(e) => updateField('salaryMin', e.target.value)}
                placeholder="160000"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Max Salary
            </label>
            <div className="flex gap-1 items-center">
              <span className="text-gray-500 dark:text-gray-400">$</span>
              <input
                type="number"
                value={formData.salaryMax}
                onChange={(e) => updateField('salaryMax', e.target.value)}
                placeholder="300000"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Salary Period
            </label>
            <select
              value={formData.salaryPeriod}
              onChange={(e) => updateField('salaryPeriod', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
            >
              {SALARY_PERIOD_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        <TagInput
          label="Preferred Locations"
          value={formData.locations}
          onChange={(v) => updateField('locations', v)}
          placeholder="Remote, New York, San Francisco..."
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Job Types
          </label>
          <div className="flex flex-wrap gap-2">
            {JOB_TYPE_OPTIONS.map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                <input
                  type="checkbox"
                  checked={formData.jobTypes.includes(opt.value)}
                  onChange={() => toggleArrayItem('jobTypes', opt.value)}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Company Sizes
          </label>
          <div className="flex flex-wrap gap-2">
            {COMPANY_SIZE_OPTIONS.map(opt => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                <input
                  type="checkbox"
                  checked={formData.companySizes.includes(opt.value)}
                  onChange={() => toggleArrayItem('companySizes', opt.value)}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      </FormSection>

      {/* Candidate Profile (Optional) */}
      <FormSection
        title="About You (Optional)"
        description="Additional context for AI matching"
      >
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Self Description
          </label>
          <textarea
            value={formData.selfDescription}
            onChange={(e) => updateField('selfDescription', e.target.value)}
            placeholder="Brief description of your background..."
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[60px]"
          />
        </div>

        <TagInput
          label="Key Strengths"
          value={formData.keyStrengths}
          onChange={(v) => updateField('keyStrengths', v)}
          placeholder="Add a strength..."
        />

        <TagInput
          label="Technical Skills"
          value={formData.technicalSkills}
          onChange={(v) => updateField('technicalSkills', v)}
          placeholder="Add a skill..."
        />
      </FormSection>
    </div>
  );
}
