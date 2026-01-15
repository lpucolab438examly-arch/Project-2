// API Types
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
  correlation_id: string;
}

// Authentication Types
export interface User {
  id: number;
  user_id: string;
  email: string;
  role: UserRole;
  full_name?: string;
  created_at: string;
  last_login?: string;
  is_active: boolean;
}

export type UserRole = 'admin' | 'fraud_analyst' | 'read_only_auditor';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: 'Bearer';
}

export interface AuthContext {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

// Transaction Types
export interface Transaction {
  id: number;
  transaction_id: string;
  user_id: string;
  amount: number;
  merchant: string;
  merchant_category: string;
  location_country?: string;
  location_city?: string;
  payment_method?: string;
  device_type?: string;
  transaction_date: string;
  is_fraud: boolean | null;
  status: 'processed' | 'pending' | 'failed';
  created_at: string;
  fraud_prediction?: FraudPrediction;
}

export interface FraudPrediction {
  id: number;
  transaction_id: number;
  model_version: string;
  fraud_probability: number;
  risk_level: 'low' | 'medium' | 'high';
  prediction_date: string;
  processing_time_ms: number;
  confidence_score?: number;
  features_used?: string[];
}

export interface TransactionFilters {
  fraud_label?: boolean | null;
  amount_min?: number;
  amount_max?: number;
  date_from?: string;
  date_to?: string;
  user_id?: string;
  merchant?: string;
  risk_level?: 'low' | 'medium' | 'high';
  page?: number;
  limit?: number;
}

export interface PaginatedTransactions {
  transactions: Transaction[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// Model Types
export interface ModelVersion {
  id: number;
  model_name: string;
  version: string;
  algorithm: string;
  hyperparameters: Record<string, any>;
  training_accuracy: number;
  validation_accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  is_active: boolean;
  created_at: string;
  artifact_path?: string;
}

export interface ModelTrainingJob {
  job_id: string;
  status: 'started' | 'running' | 'completed' | 'failed';
  progress: number;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  model_version?: string;
  metrics?: ModelMetrics;
  error_message?: string;
}

export interface ModelMetrics {
  training_accuracy: number;
  validation_accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  auc_roc: number;
  confusion_matrix: {
    true_positive: number;
    true_negative: number;
    false_positive: number;
    false_negative: number;
  };
  feature_importance?: Array<{
    feature: string;
    importance: number;
  }>;
}

// Dashboard Types
export interface DashboardStats {
  total_transactions_24h: number;
  fraud_rate_24h: number;
  total_amount_24h: number;
  avg_processing_time: number;
  active_model_accuracy: number;
  fraud_alerts_count: number;
  system_health: 'healthy' | 'warning' | 'critical';
}

export interface FraudAlert {
  id: number;
  transaction_id: string;
  user_id: string;
  fraud_probability: number;
  amount: number;
  merchant: string;
  risk_level: 'medium' | 'high';
  created_at: string;
  status: 'new' | 'investigating' | 'resolved' | 'false_positive';
  assigned_to?: string;
}

export interface ChartDataPoint {
  timestamp: string;
  date: string;
  fraud_rate: number;
  transaction_count: number;
  total_amount: number;
  avg_amount: number;
}

// Audit Log Types
export interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  user_id: string;
  changes: Record<string, any>;
  ip_address: string;
  user_agent: string;
  timestamp: string;
  checksum: string;
}

export interface AuditFilters {
  entity_type?: string;
  action?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}

// Health Check Types
export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  uptime_seconds: number;
  system: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
  };
  dependencies: {
    database: HealthCheck;
    redis: HealthCheck;
    model: HealthCheck;
  };
  cache: {
    hit_rate: number;
    size_mb: number;
    evictions: number;
  };
}

export interface HealthCheck {
  status: 'healthy' | 'unhealthy';
  response_time_ms: number;
  last_check: string;
  details?: Record<string, any>;
}

// API Client Types
export interface ApiClientConfig {
  baseURL: string;
  timeout: number;
  withCredentials: boolean;
}

// Form Types
export interface CreateTransactionForm {
  user_id: string;
  amount: number;
  merchant: string;
  merchant_category: string;
  location_country?: string;
  location_city?: string;
  payment_method?: string;
  device_type?: string;
}

export interface LoginForm {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface ModelTrainingForm {
  algorithm: 'randomforest' | 'xgboost' | 'lightgbm';
  hyperparameters?: Record<string, any>;
  training_data_days?: number;
  validation_split?: number;
}

// Notification Types
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  action?: {
    label: string;
    url: string;
  };
}

// Component Props Types
export interface TableColumn<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  render?: (value: any, row: T) => React.ReactNode;
  width?: string;
}

export interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  loading?: boolean;
  pagination?: {
    page: number;
    limit: number;
    total: number;
    onPageChange: (page: number) => void;
  };
  sorting?: {
    column: keyof T | null;
    direction: 'asc' | 'desc';
    onSort: (column: keyof T) => void;
  };
}

// WebSocket Types
export interface WebSocketMessage {
  type: 'fraud_alert' | 'system_status' | 'model_update' | 'heartbeat';
  payload: any;
  timestamp: string;
}

// Theme Types
export interface ThemeContext {
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}