export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface TaskResponse {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: {
    current: number;
    total: number;
    message?: string;
  };
  result?: unknown;
  error?: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  components: {
    database: boolean;
    llama_server: boolean;
  };
}

export interface Profile {
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
}
