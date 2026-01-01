import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Add auth token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('mcp_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Error handling interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Could redirect to auth or show modal
      console.warn('Authentication required');
    }
    return Promise.reject(error);
  }
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function handleApiError(error: unknown): never {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.detail || error.response?.data?.error || error.message;
    throw new ApiError(message, error.response?.status, error.response?.data);
  }
  throw error;
}
