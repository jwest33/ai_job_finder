import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import {
  ApplicationStatus,
  APPLICATION_STATUS_LABELS,
  APPLICATION_STATUS_COLORS,
} from '../../types/job';
import clsx from 'clsx';

interface JobStatusDropdownProps {
  status: ApplicationStatus;
  onChange: (status: ApplicationStatus) => void;
  disabled?: boolean;
}

const STATUS_ORDER: ApplicationStatus[] = [
  'not_applied',
  'applied',
  'phone_screen',
  'interviewing',
  'final_round',
  'offer',
  'rejected',
  'withdrawn',
  'no_response',
];

export function JobStatusDropdown({ status, onChange, disabled }: JobStatusDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (newStatus: ApplicationStatus) => {
    onChange(newStatus);
    setIsOpen(false);
  };

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors',
          APPLICATION_STATUS_COLORS[status],
          disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:opacity-80'
        )}
      >
        {APPLICATION_STATUS_LABELS[status]}
        {!disabled && <ChevronDown className="w-3 h-3" />}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1 w-40 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
          {STATUS_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => handleSelect(s)}
              className="w-full flex items-center justify-between px-3 py-1.5 text-xs hover:bg-gray-50"
            >
              <span className={clsx('px-2 py-0.5 rounded-full', APPLICATION_STATUS_COLORS[s])}>
                {APPLICATION_STATUS_LABELS[s]}
              </span>
              {s === status && <Check className="w-3 h-3 text-blue-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
