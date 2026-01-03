import { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, RefreshCw } from 'lucide-react';
import { TagInput } from '../common/TagInput';
import { Button } from '../common/Button';
import { templatesApi } from '../../api/templates';
import type { ParsedResume, ExperienceEntry, EducationEntry } from '../../types/template';

interface ResumeFormEditorProps {
  content: string;
  onChange: (content: string) => void;
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

// Form Section Component
function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      </div>
      <div className="p-4 space-y-4">
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
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
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
    <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50">
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
        <button onClick={onDelete} className="ml-2 p-2 text-red-500 hover:bg-red-50 rounded">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Accomplishments</label>
        <div className="space-y-2">
          {entry.bullets.map((bullet, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-gray-400 mt-2">•</span>
              <input
                type="text"
                value={bullet}
                onChange={(e) => updateBullet(index, e.target.value)}
                placeholder="Describe your accomplishment..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <button onClick={() => removeBullet(index)} className="p-2 text-gray-400 hover:text-red-500">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        <button onClick={addBullet} className="mt-2 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1">
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
    <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
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
        <button onClick={onDelete} className="mt-6 p-2 text-red-500 hover:bg-red-50 rounded">
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
export function ResumeFormEditor({ content, onChange }: ResumeFormEditorProps) {
  const [formData, setFormData] = useState<LocalFormData>(emptyFormData());
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [hasParsed, setHasParsed] = useState(false);

  // Parse resume when component mounts or content changes significantly
  const parseResume = async () => {
    if (!content.trim()) {
      setFormData(emptyFormData());
      setHasParsed(true);
      return;
    }

    setIsParsing(true);
    setParseError(null);

    try {
      const parsed = await templatesApi.parseResume();
      setFormData(toLocalFormData(parsed));
      setHasParsed(true);
    } catch (error) {
      console.error('Failed to parse resume:', error);
      setParseError(error instanceof Error ? error.message : 'Failed to parse resume');
      // Keep existing form data on error
    } finally {
      setIsParsing(false);
    }
  };

  // Parse on initial mount if there's content
  useEffect(() => {
    if (content.trim() && !hasParsed) {
      parseResume();
    }
  }, []);

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

  // Loading state
  if (isParsing) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px] text-gray-500">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-4" />
        <p className="text-sm">Parsing resume with AI...</p>
        <p className="text-xs text-gray-400 mt-1">This may take a few seconds</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
      {/* Parse Error / Re-parse Button */}
      {parseError && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center justify-between">
          <p className="text-sm text-yellow-800">{parseError}</p>
          <Button variant="secondary" size="sm" onClick={parseResume}>
            <RefreshCw className="w-4 h-4 mr-1" /> Retry
          </Button>
        </div>
      )}

      {/* Re-parse button for when user wants to re-analyze */}
      {!parseError && hasParsed && (
        <div className="flex justify-end">
          <button
            onClick={parseResume}
            className="text-xs text-gray-500 hover:text-blue-600 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Re-parse with AI
          </button>
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
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm min-h-[100px]"
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
