import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import Cookies from 'js-cookie'
import { 
  ApiResponse, 
  AuthTokens, 
  LoginCredentials, 
  User,
  Transaction,
  PaginatedTransactions,
  TransactionFilters,
  CreateTransactionForm,
  ModelVersion,
  ModelTrainingJob,
  ModelTrainingForm,
  DashboardStats,
  FraudAlert,
  AuditLog,
  AuditFilters,
  SystemHealth,
  ChartDataPoint
} from '@/types'

class ApiClient {
  private client: AxiosInstance
  private refreshing = false
  private failedQueue: Array<{
    resolve: (value: string) => void
    reject: (error: any) => void
  }> = []

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        
        // Add correlation ID for tracing
        config.headers['X-Correlation-ID'] = this.generateCorrelationId()
        
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const original = error.config

        if (error.response?.status === 401 && !original._retry) {
          if (this.refreshing) {
            // If already refreshing, queue the request
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject })
            })
              .then((token) => {
                original.headers.Authorization = `Bearer ${token}`
                return this.client(original)
              })
              .catch((err) => {
                return Promise.reject(err)
              })
          }

          original._retry = true
          this.refreshing = true

          try {
            const newToken = await this.refreshToken()
            this.refreshing = false
            
            // Process the failed queue
            this.failedQueue.forEach(({ resolve }) => resolve(newToken))
            this.failedQueue = []

            original.headers.Authorization = `Bearer ${newToken}`
            return this.client(original)
          } catch (refreshError) {
            this.refreshing = false
            this.failedQueue.forEach(({ reject }) => reject(refreshError))
            this.failedQueue = []
            
            // Redirect to login
            this.clearTokens()
            window.location.href = '/login'
            return Promise.reject(refreshError)
          }
        }

        return Promise.reject(error)
      }
    )
  }

  private generateCorrelationId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
  }

  private getAccessToken(): string | null {
    return Cookies.get('access_token') || null
  }

  private getRefreshToken(): string | null {
    return Cookies.get('refresh_token') || null
  }

  private setTokens(tokens: AuthTokens): void {
    const expires = new Date(Date.now() + tokens.expires_in * 1000)
    
    Cookies.set('access_token', tokens.access_token, { 
      expires, 
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax'
    })
    
    Cookies.set('refresh_token', tokens.refresh_token, { 
      expires: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax'
    })
  }

  private clearTokens(): void {
    Cookies.remove('access_token')
    Cookies.remove('refresh_token')
  }

  // Auth endpoints
  async login(credentials: LoginCredentials): Promise<{ user: User; tokens: AuthTokens }> {
    const response = await this.client.post<ApiResponse<{ user: User; tokens: AuthTokens }>>(
      '/api/v1/auth/login',
      credentials
    )
    
    if (response.data.status === 'success' && response.data.data) {
      this.setTokens(response.data.data.tokens)
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Login failed')
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/v1/auth/logout')
    } finally {
      this.clearTokens()
    }
  }

  async refreshToken(): Promise<string> {
    const refreshToken = this.getRefreshToken()
    if (!refreshToken) {
      throw new Error('No refresh token available')
    }

    const response = await this.client.post<ApiResponse<AuthTokens>>(
      '/api/v1/auth/refresh',
      { refresh_token: refreshToken }
    )

    if (response.data.status === 'success' && response.data.data) {
      this.setTokens(response.data.data)
      return response.data.data.access_token
    }

    throw new Error(response.data.error || 'Token refresh failed')
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<ApiResponse<User>>('/api/v1/auth/me')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get current user')
  }

  // Dashboard endpoints
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await this.client.get<ApiResponse<DashboardStats>>('/api/v1/dashboard/stats')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get dashboard stats')
  }

  async getFraudAlerts(): Promise<FraudAlert[]> {
    const response = await this.client.get<ApiResponse<FraudAlert[]>>('/api/v1/dashboard/alerts')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get fraud alerts')
  }

  async getChartData(days: number = 7): Promise<ChartDataPoint[]> {
    const response = await this.client.get<ApiResponse<ChartDataPoint[]>>(
      `/api/v1/dashboard/chart-data?days=${days}`
    )
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get chart data')
  }

  // Transaction endpoints
  async getTransactions(filters: TransactionFilters = {}): Promise<PaginatedTransactions> {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value))
      }
    })

    const response = await this.client.get<ApiResponse<PaginatedTransactions>>(
      `/api/v1/transactions?${params.toString()}`
    )
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get transactions')
  }

  async getTransaction(id: number): Promise<Transaction> {
    const response = await this.client.get<ApiResponse<Transaction>>(`/api/v1/transactions/${id}`)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get transaction')
  }

  async createTransaction(data: CreateTransactionForm): Promise<Transaction> {
    const response = await this.client.post<ApiResponse<Transaction>>('/api/v1/transactions', data)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to create transaction')
  }

  async rerunPrediction(transactionId: number): Promise<Transaction> {
    const response = await this.client.post<ApiResponse<Transaction>>(
      `/api/v1/transactions/${transactionId}/predict`
    )
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to rerun prediction')
  }

  // Model endpoints
  async getModels(): Promise<ModelVersion[]> {
    const response = await this.client.get<ApiResponse<ModelVersion[]>>('/api/v1/models')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data.models || response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get models')
  }

  async getModel(version: string): Promise<ModelVersion> {
    const response = await this.client.get<ApiResponse<ModelVersion>>(`/api/v1/models/${version}`)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get model')
  }

  async getModelMetrics(version: string): Promise<any> {
    const response = await this.client.get<ApiResponse<any>>(`/api/v1/models/${version}/metrics`)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get model metrics')
  }

  async trainModel(data: ModelTrainingForm): Promise<ModelTrainingJob> {
    const response = await this.client.post<ApiResponse<ModelTrainingJob>>('/api/v1/models/train', data)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to start model training')
  }

  async getTrainingJob(jobId: string): Promise<ModelTrainingJob> {
    const response = await this.client.get<ApiResponse<ModelTrainingJob>>(`/api/v1/models/train/${jobId}`)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get training job')
  }

  async activateModel(version: string): Promise<void> {
    const response = await this.client.post<ApiResponse<void>>(`/api/v1/models/${version}/activate`)
    
    if (response.data.status !== 'success') {
      throw new Error(response.data.error || 'Failed to activate model')
    }
  }

  // Audit endpoints
  async getAuditLogs(filters: AuditFilters = {}): Promise<{ logs: AuditLog[]; total: number }> {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value))
      }
    })

    const response = await this.client.get<ApiResponse<{ logs: AuditLog[]; total: number }>>(
      `/api/v1/audit?${params.toString()}`
    )
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get audit logs')
  }

  // Health endpoints
  async getSystemHealth(): Promise<SystemHealth> {
    const response = await this.client.get<ApiResponse<SystemHealth>>('/api/v1/health/detailed')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get system health')
  }

  // User management endpoints
  async getUsers(): Promise<User[]> {
    const response = await this.client.get<ApiResponse<User[]>>('/api/v1/users')
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to get users')
  }

  async createUser(userData: Partial<User>): Promise<User> {
    const response = await this.client.post<ApiResponse<User>>('/api/v1/users', userData)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to create user')
  }

  async updateUser(id: number, userData: Partial<User>): Promise<User> {
    const response = await this.client.put<ApiResponse<User>>(`/api/v1/users/${id}`, userData)
    
    if (response.data.status === 'success' && response.data.data) {
      return response.data.data
    }
    
    throw new Error(response.data.error || 'Failed to update user')
  }

  async deleteUser(id: number): Promise<void> {
    const response = await this.client.delete<ApiResponse<void>>(`/api/v1/users/${id}`)
    
    if (response.data.status !== 'success') {
      throw new Error(response.data.error || 'Failed to delete user')
    }
  }

  // Utility methods
  isAuthenticated(): boolean {
    return !!this.getAccessToken()
  }

  async downloadCSV(endpoint: string, filename: string): Promise<void> {
    const response = await this.client.get(endpoint, {
      responseType: 'blob',
      headers: {
        'Accept': 'text/csv'
      }
    })

    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}

// Create and export a singleton instance
export const apiClient = new ApiClient()
export default apiClient