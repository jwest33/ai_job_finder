import { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { TagInput } from '../common/TagInput';
import { Button } from '../common/Button';
import { templatesApi } from '../../api/templates';
import type { ParsedResume, ExperienceEntry, EducationEntry, ATSScoreResult, ATSCategoryResult } from '../../types/template';
import clsx from 'clsx';

interface ResumeFormEditorProps {
  content: string;
  onChange: (content: string) => void;
  onAnalyze?: () => void;
  isAnalyzing?: boolean;
  isLoadingCachedScore?: boolean;
  atsScore?: ATSScoreResult | null;
  onClearAtsScore?: () => void;
}

// Generate unique IDs
const generateId = () => Math.random().toString(36).substring(2, 9);

// Local form data with IDs for React keys
interface LocalExperience extends ExperienceEntry {
  id: string;
}

interface LocalEducation extends EducationEntry {
  id: string;
}

interface LocalFormData {
  contact: ParsedResume['contact'];
  summary: string;
  experience: LocalExperience[];
  education: LocalEducation[];
  skills: string[];
  certifications: string[];
  languages: string[];
}

// Convert parsed resume to local form data with IDs
function toLocalFormData(parsed: ParsedResume): LocalFormData {
  return {
    contact: parsed.contact,
    summary: parsed.summary,
    experience: parsed.experience.map(exp => ({ ...exp, id: generateId() })),
    education: parsed.education.map(edu => ({ ...edu, id: generateId() })),
    skills: parsed.skills,
    certifications: parsed.certifications,
    languages: parsed.languages
  };
}

// Serialize form data back to plain text
function serializeToText(data: LocalFormData): string {
  const lines: string[] = [];

  // Contact info
  if (data.contact.name) lines.push(data.contact.name);

  const contactLine = [
    data.contact.email,
    data.contact.phone,
    data.contact.location
  ].filter(Boolean).join(' | ');
  if (contactLine) lines.push(contactLine);

  if (data.contact.linkedin) lines.push(data.contact.linkedin);
  if (data.contact.website) lines.push(data.contact.website);

  lines.push('');

  // Summary
  if (data.summary) {
    lines.push(data.summary);
    lines.push('');
  }

  // Experience
  if (data.experience.length > 0) {
    lines.push('EXPERIENCE');
    lines.push('');

    for (const job of data.experience) {
      const titleLine = [job.title, job.company].filter(Boolean).join(' | ');
      const dateLine = [job.start_date, job.end_date].filter(Boolean).join(' - ');
      let fullLine = titleLine;
      if (dateLine) fullLine += ` | ${dateLine}`;
      if (job.location) fullLine += ` | ${job.location}`;
      if (fullLine) lines.push(fullLine);

      for (const bullet of job.bullets) {
        if (bullet.trim()) lines.push(`• ${bullet}`);
      }
      lines.push('');
    }
  }

  // Education
  if (data.education.length > 0) {
    lines.push('EDUCATION');
    lines.push('');

    for (const edu of data.education) {
      const parts = [edu.degree, edu.school, edu.year].filter(Boolean);
      if (edu.gpa) parts.push(`GPA: ${edu.gpa}`);
      lines.push(parts.join(', '));
      if (edu.honors) lines.push(`  ${edu.honors}`);
    }
    lines.push('');
  }

  // Skills
  if (data.skills.length > 0) {
    lines.push('SKILLS');
    lines.push('');
    lines.push(data.skills.join(', '));
    lines.push('');
  }

  // Certifications
  if (data.certifications.length > 0) {
    lines.push('CERTIFICATIONS');
    lines.push('');
    for (const cert of data.certifications) {
      lines.push(`• ${cert}`);
    }
    lines.push('');
  }

  // Languages
  if (data.languages.length > 0) {
    lines.push('LANGUAGES');
    lines.push('');
    lines.push(data.languages.join(', '));
  }

  return lines.join('\n').trim();
}

// Empty form data
function emptyFormData(): LocalFormData {
  return {
    contact: { name: '', email: '', phone: '', location: '', linkedin: '', website: '' },
    summary: '',
    experience: [],
    education: [],
    skills: [],
    certifications: [],
    languages: []
  };
}

// ATS Score helpers
const CATEGORY_LABELS: Record<string, string> = {
  keywords: 'Keywords',
  formatting: 'Formatting',
  sections: 'Section Structure',
  achievements: 'Achievements',
  contact_info: 'Contact Info',
  skills: 'Skills',
};

function getScoreColor(score: number): string {
  if (score >= 90) return 'text-green-600 dark:text-green-400';
  if (score >= 70) return 'text-blue-600 dark:text-blue-400';
  if (score >= 50) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function getScoreBgColor(score: number): string {
  if (score >= 90) return 'bg-green-500';
  if (score >= 70) return 'bg-blue-500';
  if (score >= 50) return 'bg-yellow-500';
  return 'bg-red-500';
}

function ATSCategoryCard({ name, data }: { name: string; data: ATSCategoryResult }) {
  const [expanded, setExpanded] = useState(false);
  const hasIssues = data.issues.length > 0;
  const hasRecommendations = data.recommendations.length > 0;

  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-700"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{CATEGORY_LABELS[name] || name}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full', getScoreBgColor(data.score))}
                style={{ width: `${data.score}%` }}
              />
            </div>
            <span className={clsx('text-sm font-bold w-8', getScoreColor(data.score))}>
              {data.score}
            </span>
          </div>
          {(hasIssues || hasRecommendations) && (
            expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>
      {expanded && (hasIssues || hasRecommendations) && (
        <div className="px-3 pb-3 space-y-3 bg-white dark:bg-gray-800">
          {hasIssues && (
            <div>
              <h4 className="text-xs font-medium text-red-600 dark:text-red-400 uppercase mb-1">Issues</h4>
              <ul className="space-y-1">
                {data.issues.map((issue, i) => (
                  <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                    <span className="text-red-400 mt-0.5">-</span>
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasRecommendations && (
            <div>
              <h4 className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase mb-1">Recommendations</h4>
              <ul className="space-y-1">
                {data.recommendations.map((rec, i) => (
                  <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">+</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ATSScorePanel({ score, onClose }: { score: ATSScoreResult; onClose: () => void }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm overflow-hidden">
      <div className="bg-gray-50 dark:bg-gray-700 px-4 py-3 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 dark:text-white">ATS Quality Score</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">
          &times;
        </button>
      </div>

      <div className="p-4 space-y-4 max-h-[600px] overflow-y-auto">
        {/* Overall Score */}
        <div className="text-center py-4">
          <div className={clsx('text-5xl font-bold', getScoreColor(score.overall_score))}>
            {score.overall_score}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">out of 100</div>
        </div>

        {/* Summary */}
        <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
          {score.summary}
        </p>

        {/* Category Breakdown */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Category Scores</h4>
          <div className="space-y-2">
            {Object.entries(score.categories).map(([name, data]) => (
              <ATSCategoryCard key={name} name={name} data={data} />
            ))}
          </div>
        </div>

        {/* Top Recommendations */}
        {score.top_recommendations.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Top Recommendations</h4>
            <ul className="space-y-2">
              {score.top_recommendations.map((rec, i) => (
                <li key={i} className="text-sm text-gray-600 dark:text-gray-300 flex items-start gap-2 bg-blue-50 dark:bg-blue-900/30 p-2 rounded">
                  <span className="text-blue-500 dark:text-blue-400 font-bold">{i + 1}.</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// Form Section Component
function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="bg-gray-50 dark:bg-gray-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h3>
      </div>
      <div className="p-4 space-y-4 bg-white dark:bg-gray-800">
        {children}
      </div>
    </div>
  );
}

// Input Field Component
function FormField({ label, value, onChange, placeholder, type = 'text' }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
      />
    </div>
  );
}

// Experience Entry Component
function ExperienceEntryForm({ entry, onChange, onDelete }: {
  entry: LocalExperience;
  onChange: (entry: LocalExperience) => void;
  onDelete: () => void;
}) {
  const addBullet = () => {
    onChange({ ...entry, bullets: [...entry.bullets, ''] });
  };

  const updateBullet = (index: number, value: string) => {
    const newBullets = [...entry.bullets];
    newBullets[index] = value;
    onChange({ ...entry, bullets: newBullets });
  };

  const removeBullet = (index: number) => {
    onChange({ ...entry, bullets: entry.bullets.filter((_, i) => i !== index) });
  };

  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 space-y-3 bg-gray-50 dark:bg-gray-700/50">
      <div className="flex justify-between items-start">
        <div className="grid grid-cols-2 gap-3 flex-1">
          <FormField
            label="Job Title"
            value={entry.title}
            onChange={(v) => onChange({ ...entry, title: v })}
            placeholder="Software Engineer"
          />
          <FormField
            label="Company"
            value={entry.company}
            onChange={(v) => onChange({ ...entry, company: v })}
            placeholder="Acme Inc."
          />
          <FormField
            label="Start Date"
            value={entry.start_date}
            onChange={(v) => onChange({ ...entry, start_date: v })}
            placeholder="Jan 2020"
          />
          <FormField
            label="End Date"
            value={entry.end_date}
            onChange={(v) => onChange({ ...entry, end_date: v })}
            placeholder="Present"
          />
          <FormField
            label="Location"
            value={entry.location}
            onChange={(v) => onChange({ ...entry, location: v })}
            placeholder="San Francisco, CA"
          />
        </div>
        <button onClick={onDelete} className="ml-2 p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Accomplishments</label>
        <div className="space-y-2">
          {entry.bullets.map((bullet, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-gray-400 mt-2">•</span>
              <input
                type="text"
                value={bullet}
                onChange={(e) => updateBullet(index, e.target.value)}
                placeholder="Describe your accomplishment..."
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <button onClick={() => removeBullet(index)} className="p-2 text-gray-400 hover:text-red-500">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        <button onClick={addBullet} className="mt-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 flex items-center gap-1">
          <Plus className="w-4 h-4" /> Add accomplishment
        </button>
      </div>
    </div>
  );
}

// Education Entry Component
function EducationEntryForm({ entry, onChange, onDelete }: {
  entry: LocalEducation;
  onChange: (entry: LocalEducation) => void;
  onDelete: () => void;
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50 space-y-3">
      <div className="flex gap-3 items-start">
        <div className="grid grid-cols-3 gap-3 flex-1">
          <FormField
            label="Degree"
            value={entry.degree}
            onChange={(v) => onChange({ ...entry, degree: v })}
            placeholder="B.S. Computer Science"
          />
          <FormField
            label="School"
            value={entry.school}
            onChange={(v) => onChange({ ...entry, school: v })}
            placeholder="University Name"
          />
          <FormField
            label="Year"
            value={entry.year}
            onChange={(v) => onChange({ ...entry, year: v })}
            placeholder="2020"
          />
        </div>
        <button onClick={onDelete} className="mt-6 p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <FormField
          label="GPA"
          value={entry.gpa}
          onChange={(v) => onChange({ ...entry, gpa: v })}
          placeholder="3.8"
        />
        <FormField
          label="Honors"
          value={entry.honors}
          onChange={(v) => onChange({ ...entry, honors: v })}
          placeholder="Magna Cum Laude"
        />
      </div>
    </div>
  );
}

// Main Component
export function ResumeFormEditor({ content, onChange, onAnalyze, isAnalyzing, isLoadingCachedScore, atsScore, onClearAtsScore }: ResumeFormEditorProps) {
  const [formData, setFormData] = useState<LocalFormData>(emptyFormData());
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [hasParsed, setHasParsed] = useState(false);

  // Combined analyze function - parses resume and triggers ATS scoring
  const analyzeResume = async () => {
    if (!content.trim()) {
      setFormData(emptyFormData());
      setHasParsed(true);
      return;
    }

    setIsParsing(true);
    setParseError(null);

    try {
      // Parse the resume into structured form
      const parsed = await templatesApi.parseResume();
      setFormData(toLocalFormData(parsed));
      setHasParsed(true);

      // Also trigger ATS scoring
      onAnalyze?.();
    } catch (error) {
      console.error('Failed to parse resume:', error);
      setParseError(error instanceof Error ? error.message : 'Failed to parse resume');
    } finally {
      setIsParsing(false);
    }
  };

  // Update parent when form data changes (but not during parsing)
  useEffect(() => {
    if (hasParsed && !isParsing) {
      const serialized = serializeToText(formData);
      onChange(serialized);
    }
  }, [formData, hasParsed, isParsing]);

  const updateContact = (field: keyof LocalFormData['contact'], value: string) => {
    setFormData(prev => ({
      ...prev,
      contact: { ...prev.contact, [field]: value }
    }));
  };

  const addExperience = () => {
    setFormData(prev => ({
      ...prev,
      experience: [...prev.experience, {
        id: generateId(),
        title: '',
        company: '',
        start_date: '',
        end_date: '',
        location: '',
        bullets: ['']
      }]
    }));
  };

  const updateExperience = (index: number, entry: LocalExperience) => {
    setFormData(prev => ({
      ...prev,
      experience: prev.experience.map((e, i) => i === index ? entry : e)
    }));
  };

  const removeExperience = (index: number) => {
    setFormData(prev => ({
      ...prev,
      experience: prev.experience.filter((_, i) => i !== index)
    }));
  };

  const addEducation = () => {
    setFormData(prev => ({
      ...prev,
      education: [...prev.education, {
        id: generateId(),
        degree: '',
        school: '',
        year: '',
        gpa: '',
        honors: ''
      }]
    }));
  };

  const updateEducation = (index: number, entry: LocalEducation) => {
    setFormData(prev => ({
      ...prev,
      education: prev.education.map((e, i) => i === index ? entry : e)
    }));
  };

  const removeEducation = (index: number) => {
    setFormData(prev => ({
      ...prev,
      education: prev.education.filter((_, i) => i !== index)
    }));
  };

  const isWorking = isParsing || isAnalyzing;

  // Show loading state while fetching cached ATS score
  if (isLoadingCachedScore) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] text-gray-500 dark:text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p className="text-sm">Loading cached ATS score...</p>
      </div>
    );
  }

  // Show analyze prompt if not yet parsed AND no cached ATS score
  if (!hasParsed && !isParsing && !atsScore) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] text-gray-500 dark:text-gray-400 p-8">
        <Zap className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-4" />
        <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">Analyze Your Resume</h3>
        <p className="text-sm text-center text-gray-500 dark:text-gray-400 mb-6 max-w-md">
          Click the button below to parse your resume into structured fields and get an ATS compatibility score.
        </p>
        <Button
          onClick={analyzeResume}
          disabled={!content.trim()}
          loading={false}
        >
          <Zap className="w-4 h-4 mr-2" />
          Analyze Resume
        </Button>
        {!content.trim() && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
            Add resume content in Raw view first, then switch back to Form view to analyze.
          </p>
        )}
      </div>
    );
  }

  // Show cached ATS score with option to parse for form editing
  if (!hasParsed && !isParsing && atsScore) {
    return (
      <div className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
        {/* Show cached ATS Score Panel */}
        {onClearAtsScore && (
          <ATSScorePanel score={atsScore} onClose={onClearAtsScore} />
        )}

        {/* Prompt to parse for form editing */}
        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-center">
          <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
            Want to edit your resume in form view? Click below to parse the content.
          </p>
          <Button
            onClick={analyzeResume}
            disabled={!content.trim()}
            variant="secondary"
          >
            <Zap className="w-4 h-4 mr-2" />
            Parse Resume for Editing
          </Button>
        </div>
      </div>
    );
  }

  // Loading state
  if (isWorking) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] text-gray-500 dark:text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p className="text-sm">{isParsing ? 'Parsing resume...' : 'Analyzing ATS compatibility...'}</p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">This may take a few seconds</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
      {/* ATS Score Panel */}
      {atsScore && onClearAtsScore && (
        <ATSScorePanel score={atsScore} onClose={onClearAtsScore} />
      )}

      {/* Parse Error */}
      {parseError && (
        <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 flex items-center justify-between">
          <p className="text-sm text-yellow-800 dark:text-yellow-300">{parseError}</p>
          <Button variant="secondary" size="sm" onClick={analyzeResume}>
            <Zap className="w-4 h-4 mr-1" /> Retry
          </Button>
        </div>
      )}

      {/* Re-analyze button */}
      {!parseError && hasParsed && (
        <div className="flex justify-end">
          <Button
            variant="secondary"
            size="sm"
            onClick={analyzeResume}
            disabled={isWorking}
          >
            <Zap className="w-4 h-4 mr-1" /> Re-analyze
          </Button>
        </div>
      )}

      {/* Contact Info */}
      <FormSection title="Contact Information">
        <div className="grid grid-cols-2 gap-4">
          <FormField
            label="Full Name"
            value={formData.contact.name}
            onChange={(v) => updateContact('name', v)}
            placeholder="John Smith"
          />
          <FormField
            label="Email"
            value={formData.contact.email}
            onChange={(v) => updateContact('email', v)}
            placeholder="john@example.com"
            type="email"
          />
          <FormField
            label="Phone"
            value={formData.contact.phone}
            onChange={(v) => updateContact('phone', v)}
            placeholder="(555) 123-4567"
            type="tel"
          />
          <FormField
            label="Location"
            value={formData.contact.location}
            onChange={(v) => updateContact('location', v)}
            placeholder="New York, NY"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <FormField
            label="LinkedIn"
            value={formData.contact.linkedin}
            onChange={(v) => updateContact('linkedin', v)}
            placeholder="linkedin.com/in/yourprofile"
          />
          <FormField
            label="Website"
            value={formData.contact.website}
            onChange={(v) => updateContact('website', v)}
            placeholder="yourwebsite.com"
          />
        </div>
      </FormSection>

      {/* Summary */}
      <FormSection title="Professional Summary">
        <textarea
          value={formData.summary}
          onChange={(e) => setFormData(prev => ({ ...prev, summary: e.target.value }))}
          placeholder="A brief summary of your professional background and career objectives..."
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[100px]"
        />
      </FormSection>

      {/* Experience */}
      <FormSection title="Work Experience">
        <div className="space-y-4">
          {formData.experience.map((entry, index) => (
            <ExperienceEntryForm
              key={entry.id}
              entry={entry}
              onChange={(e) => updateExperience(index, e)}
              onDelete={() => removeExperience(index)}
            />
          ))}
        </div>
        <Button variant="secondary" onClick={addExperience}>
          <Plus className="w-4 h-4 mr-2" /> Add Experience
        </Button>
      </FormSection>

      {/* Education */}
      <FormSection title="Education">
        <div className="space-y-4">
          {formData.education.map((entry, index) => (
            <EducationEntryForm
              key={entry.id}
              entry={entry}
              onChange={(e) => updateEducation(index, e)}
              onDelete={() => removeEducation(index)}
            />
          ))}
        </div>
        <Button variant="secondary" onClick={addEducation}>
          <Plus className="w-4 h-4 mr-2" /> Add Education
        </Button>
      </FormSection>

      {/* Skills */}
      <FormSection title="Skills">
        <TagInput
          value={formData.skills}
          onChange={(skills) => setFormData(prev => ({ ...prev, skills }))}
          placeholder="Add a skill..."
        />
      </FormSection>

      {/* Certifications */}
      <FormSection title="Certifications">
        <TagInput
          value={formData.certifications}
          onChange={(certifications) => setFormData(prev => ({ ...prev, certifications }))}
          placeholder="Add a certification..."
        />
      </FormSection>

      {/* Languages */}
      <FormSection title="Languages">
        <TagInput
          value={formData.languages}
          onChange={(languages) => setFormData(prev => ({ ...prev, languages }))}
          placeholder="Add a language..."
        />
      </FormSection>
    </div>
  );
}
