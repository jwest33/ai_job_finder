// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Pagination
export const DEFAULT_PAGE_SIZE = 25;
export const MAX_PAGE_SIZE = 100;

// Score thresholds
export const SCORE_THRESHOLDS = {
  EXCELLENT: 80,
  GOOD: 60,
  FAIR: 40,
} as const;

// Job sources
export const JOB_SOURCES = ['indeed', 'glassdoor'] as const;

// Local storage keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'mcp_auth_token',
  THEME: 'theme',
  SIDEBAR_STATE: 'sidebar_open',
} as const;

// Keyboard shortcuts
export const KEYBOARD_SHORTCUTS = {
  SEARCH: 'mod+k',
  ESCAPE: 'escape',
} as const;
