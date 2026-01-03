import { useState, useEffect } from 'react';
import { TagInput } from '../common/TagInput';
import yaml from 'js-yaml';

interface RequirementsFormData {
  selfDescription: string;
  keyStrengths: string[];
  technicalSkills: string[];
  careerGoals: string;
  mustHaves: string[];
  avoidList: string[];
  targetRoles: string[];
  searchTerms: string[];
  requiredSkills: string[];
  preferredSkills: string[];
  remotePreference: string;
  salaryMin: string;
  salaryMax: string;
  locations: string[];
}

interface RequirementsFormEditorProps {
  content: string;
  onChange: (content: string) => void;
}

const REMOTE_OPTIONS = [
  { value: '', label: 'Any' },
  { value: 'remote', label: 'Remote Only' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'onsite', label: 'On-site Only' },
];

// Parse YAML content to form data
function parseRequirements(content: string): RequirementsFormData {
  const defaults: RequirementsFormData = {
    selfDescription: '',
    keyStrengths: [],
    technicalSkills: [],
    careerGoals: '',
    mustHaves: [],
    avoidList: [],
    targetRoles: [],
    searchTerms: [],
    requiredSkills: [],
    preferredSkills: [],
    remotePreference: '',
    salaryMin: '',
    salaryMax: '',
    locations: []
  };

  try {
    const data = yaml.load(content) as Record<string, unknown>;
    if (!data || typeof data !== 'object') return defaults;

    const profile = (data.candidate_profile || {}) as Record<string, unknown>;
    const requirements = (data.job_requirements || {}) as Record<string, unknown>;
    const preferences = (data.preferences || {}) as Record<string, unknown>;
    const salaryRange = (preferences.salary_range || {}) as Record<string, unknown>;

    return {
      selfDescription: String(profile.self_description || ''),
      keyStrengths: Array.isArray(profile.key_strengths) ? profile.key_strengths : [],
      technicalSkills: Array.isArray(profile.technical_skills) ? profile.technical_skills : [],
      careerGoals: String(profile.career_goals || ''),
      mustHaves: Array.isArray(profile.must_haves) ? profile.must_haves : [],
      avoidList: Array.isArray(profile.avoid_list) ? profile.avoid_list : [],
      targetRoles: Array.isArray(requirements.target_roles) ? requirements.target_roles : [],
      searchTerms: Array.isArray(requirements.search_terms) ? requirements.search_terms : [],
      requiredSkills: Array.isArray(requirements.required_skills) ? requirements.required_skills : [],
      preferredSkills: Array.isArray(requirements.preferred_skills) ? requirements.preferred_skills : [],
      remotePreference: String(preferences.remote_preference || ''),
      salaryMin: salaryRange.min ? String(salaryRange.min) : '',
      salaryMax: salaryRange.max ? String(salaryRange.max) : '',
      locations: Array.isArray(preferences.locations) ? preferences.locations : []
    };
  } catch {
    return defaults;
  }
}

// Serialize form data to YAML
function serializeRequirements(data: RequirementsFormData): string {
  const output: Record<string, unknown> = {};

  // Candidate Profile
  const candidateProfile: Record<string, unknown> = {};
  if (data.selfDescription) candidateProfile.self_description = data.selfDescription;
  if (data.keyStrengths.length) candidateProfile.key_strengths = data.keyStrengths;
  if (data.technicalSkills.length) candidateProfile.technical_skills = data.technicalSkills;
  if (data.careerGoals) candidateProfile.career_goals = data.careerGoals;
  if (data.mustHaves.length) candidateProfile.must_haves = data.mustHaves;
  if (data.avoidList.length) candidateProfile.avoid_list = data.avoidList;

  if (Object.keys(candidateProfile).length) {
    output.candidate_profile = candidateProfile;
  }

  // Job Requirements
  const jobRequirements: Record<string, unknown> = {};
  if (data.targetRoles.length) jobRequirements.target_roles = data.targetRoles;
  if (data.searchTerms.length) jobRequirements.search_terms = data.searchTerms;
  if (data.requiredSkills.length) jobRequirements.required_skills = data.requiredSkills;
  if (data.preferredSkills.length) jobRequirements.preferred_skills = data.preferredSkills;

  if (Object.keys(jobRequirements).length) {
    output.job_requirements = jobRequirements;
  }

  // Preferences
  const preferences: Record<string, unknown> = {};
  if (data.remotePreference) preferences.remote_preference = data.remotePreference;
  if (data.locations.length) preferences.locations = data.locations;

  const salaryMin = parseInt(data.salaryMin);
  const salaryMax = parseInt(data.salaryMax);
  if (!isNaN(salaryMin) || !isNaN(salaryMax)) {
    preferences.salary_range = {};
    if (!isNaN(salaryMin)) (preferences.salary_range as Record<string, number>).min = salaryMin;
    if (!isNaN(salaryMax)) (preferences.salary_range as Record<string, number>).max = salaryMax;
  }

  if (Object.keys(preferences).length) {
    output.preferences = preferences;
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
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
      </div>
      <div className="p-4 space-y-4">
        {children}
      </div>
    </div>
  );
}

export function RequirementsFormEditor({ content, onChange }: RequirementsFormEditorProps) {
  const [formData, setFormData] = useState<RequirementsFormData>(() => parseRequirements(content));

  // Update parent when form data changes
  useEffect(() => {
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

  return (
    <div className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
      {/* Candidate Profile */}
      <FormSection
        title="About You"
        description="Describe yourself and what you're looking for"
      >
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Self Description
          </label>
          <textarea
            value={formData.selfDescription}
            onChange={(e) => updateField('selfDescription', e.target.value)}
            placeholder="Brief description of your background and what makes you a strong candidate..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[80px]"
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

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Career Goals
          </label>
          <textarea
            value={formData.careerGoals}
            onChange={(e) => updateField('careerGoals', e.target.value)}
            placeholder="What are you looking to achieve in your next role?"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[60px]"
          />
        </div>
      </FormSection>

      {/* Job Requirements */}
      <FormSection
        title="Job Search Criteria"
        description="What roles and skills are you targeting?"
      >
        <TagInput
          label="Target Roles"
          value={formData.targetRoles}
          onChange={(v) => updateField('targetRoles', v)}
          placeholder="Software Engineer, ML Engineer..."
        />

        <TagInput
          label="Search Terms"
          value={formData.searchTerms}
          onChange={(v) => updateField('searchTerms', v)}
          placeholder="Keywords to search for..."
        />

        <TagInput
          label="Required Skills"
          value={formData.requiredSkills}
          onChange={(v) => updateField('requiredSkills', v)}
          placeholder="Skills the job must require..."
        />

        <TagInput
          label="Preferred Skills"
          value={formData.preferredSkills}
          onChange={(v) => updateField('preferredSkills', v)}
          placeholder="Nice-to-have skills..."
        />
      </FormSection>

      {/* Preferences */}
      <FormSection
        title="Preferences"
        description="Your work arrangement and compensation preferences"
      >
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Remote Preference
            </label>
            <select
              value={formData.remotePreference}
              onChange={(e) => updateField('remotePreference', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
            >
              {REMOTE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Salary Range
            </label>
            <div className="flex gap-2 items-center">
              <span className="text-gray-500">$</span>
              <input
                type="number"
                value={formData.salaryMin}
                onChange={(e) => updateField('salaryMin', e.target.value)}
                placeholder="Min"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <span className="text-gray-500">-</span>
              <input
                type="number"
                value={formData.salaryMax}
                onChange={(e) => updateField('salaryMax', e.target.value)}
                placeholder="Max"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            </div>
          </div>
        </div>

        <TagInput
          label="Preferred Locations"
          value={formData.locations}
          onChange={(v) => updateField('locations', v)}
          placeholder="New York, San Francisco..."
        />
      </FormSection>

      {/* Must Haves / Avoid */}
      <FormSection
        title="Deal Breakers"
        description="Things you absolutely need or want to avoid"
      >
        <TagInput
          label="Must Haves"
          value={formData.mustHaves}
          onChange={(v) => updateField('mustHaves', v)}
          placeholder="Remote work, competitive salary..."
        />

        <TagInput
          label="Avoid List"
          value={formData.avoidList}
          onChange={(v) => updateField('avoidList', v)}
          placeholder="Contract positions, startups..."
        />
      </FormSection>
    </div>
  );
}
