'use client'

import React, { useEffect, useState } from 'react'
import { ProtectedRoute } from '@/hooks/useAuth'
import DashboardLayout from '@/components/DashboardLayout'
import { apiClient } from '@/lib/api-client'
import { DashboardMetrics } from '@/types'
import { formatCurrency, formatPercentage } from '@/lib/utils'
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const COLORS = {
  danger: '#EF4444',
  warning: '#F59E0B',
  success: '#10B981',
  info: '#3B82F6',
  muted: '#6B7280'
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const data = await apiClient.getDashboardMetrics()
        setMetrics(data)
      } catch (error: any) {
        setError(error.message || 'Failed to load dashboard metrics')
        console.error('Error fetching dashboard metrics:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchMetrics, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <ProtectedRoute>
        <DashboardLayout>
          <div className="flex items-center justify-center h-64">
            <div className="loading-spinner h-8 w-8" />
            <span className="ml-2 text-muted-foreground">Loading dashboard...</span>
          </div>
        </DashboardLayout>
      </ProtectedRoute>
    )
  }

  if (error) {
    return (
      <ProtectedRoute>
        <DashboardLayout>
          <div className="text-center py-12">
            <div className="text-red-500 mb-4">⚠️ Error loading dashboard</div>
            <p className="text-muted-foreground">{error}</p>
            <button 
              onClick={() => window.location.reload()} 
              className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary-dark"
            >
              Retry
            </button>
          </div>
        </DashboardLayout>
      </ProtectedRoute>
    )
  }

  const fraudTrendData = metrics?.fraudTrend || []
  const riskDistribution = metrics?.riskDistribution || []
  const recentTransactions = metrics?.recentTransactions || []
  const modelPerformance = metrics?.modelPerformance || {}

  return (
    <ProtectedRoute>
      <DashboardLayout>
        <div className="space-y-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Dashboard Overview</h1>
              <p className="text-muted-foreground">Real-time fraud detection insights</p>
            </div>
            <div className="flex items-center space-x-2">
              <div className="h-2 w-2 rounded-full bg-success animate-pulse" />
              <span className="text-sm text-muted-foreground">Live</span>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="Total Transactions"
              value={metrics?.totalTransactions.toLocaleString() || '0'}
              change="+12.5%"
              changeType="positive"
              icon="credit-card"
            />
            <MetricCard
              title="Fraud Detected"
              value={metrics?.fraudDetected.toLocaleString() || '0'}
              change="-2.3%"
              changeType="negative"
              icon="shield"
            />
            <MetricCard
              title="Fraud Rate"
              value={formatPercentage(metrics?.fraudRate || 0)}
              change="+0.12%"
              changeType="neutral"
              icon="chart-bar"
            />
            <MetricCard
              title="Amount Saved"
              value={formatCurrency(metrics?.amountSaved || 0)}
              change="+18.7%"
              changeType="positive"
              icon="dollar"
            />
          </div>

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Fraud Detection Trend */}
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Fraud Detection Trend</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={fraudTrendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--muted)" />
                  <XAxis dataKey="date" stroke="var(--muted-foreground)" />
                  <YAxis stroke="var(--muted-foreground)" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--card)', 
                      border: '1px solid var(--border)',
                      borderRadius: '6px'
                    }} 
                  />
                  <Area 
                    type="monotone" 
                    dataKey="legitimate" 
                    stackId="1" 
                    stroke={COLORS.success} 
                    fill={COLORS.success}
                    fillOpacity={0.6}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="fraud" 
                    stackId="1" 
                    stroke={COLORS.danger} 
                    fill={COLORS.danger}
                    fillOpacity={0.8}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Risk Score Distribution */}
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Risk Score Distribution</h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={riskDistribution}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {riskDistribution.map((entry, index) => {
                      const colors = [COLORS.success, COLORS.warning, COLORS.danger]
                      return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                    })}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Model Performance */}
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Model Performance</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Accuracy</span>
                  <span className="text-sm font-medium">{formatPercentage(modelPerformance.accuracy || 0)}</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div 
                    className="bg-success h-2 rounded-full" 
                    style={{ width: `${(modelPerformance.accuracy || 0) * 100}%` }}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Precision</span>
                  <span className="text-sm font-medium">{formatPercentage(modelPerformance.precision || 0)}</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div 
                    className="bg-info h-2 rounded-full" 
                    style={{ width: `${(modelPerformance.precision || 0) * 100}%` }}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Recall</span>
                  <span className="text-sm font-medium">{formatPercentage(modelPerformance.recall || 0)}</span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div 
                    className="bg-warning h-2 rounded-full" 
                    style={{ width: `${(modelPerformance.recall || 0) * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Recent Transactions */}
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Recent Transactions</h3>
              <div className="space-y-3">
                {recentTransactions.slice(0, 5).map((transaction, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-muted rounded-md">
                    <div className="flex-1">
                      <div className="text-sm font-medium text-foreground">
                        {formatCurrency(transaction.amount)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {transaction.merchant || 'Unknown Merchant'}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xs px-2 py-1 rounded-full ${
                        transaction.riskScore > 0.8 
                          ? 'bg-red-100 text-red-800' 
                          : transaction.riskScore > 0.5 
                          ? 'bg-yellow-100 text-yellow-800' 
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {transaction.riskScore > 0.8 ? 'High' : transaction.riskScore > 0.5 ? 'Medium' : 'Low'} Risk
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {formatPercentage(transaction.riskScore)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* System Health */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">System Status</h3>
              <div className="space-y-3">
                <StatusItem label="API Health" status="healthy" />
                <StatusItem label="Model Service" status="healthy" />
                <StatusItem label="Database" status="healthy" />
                <StatusItem label="Cache" status="warning" />
              </div>
            </div>
            
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Processing Stats</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Avg Response Time</span>
                  <span className="text-sm font-medium">45ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Requests/min</span>
                  <span className="text-sm font-medium">1,247</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Success Rate</span>
                  <span className="text-sm font-medium">99.94%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Queue Depth</span>
                  <span className="text-sm font-medium">12</span>
                </div>
              </div>
            </div>
            
            <div className="bg-card rounded-lg border border-border p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">Alerts</h3>
              <div className="space-y-3">
                <div className="flex items-start space-x-3">
                  <div className="h-2 w-2 rounded-full bg-warning mt-1.5" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">High Risk Pattern</div>
                    <div className="text-xs text-muted-foreground">Detected in region US-East</div>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="h-2 w-2 rounded-full bg-info mt-1.5" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">Model Retrained</div>
                    <div className="text-xs text-muted-foreground">Accuracy improved to 96.8%</div>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="h-2 w-2 rounded-full bg-success mt-1.5" />
                  <div className="flex-1">
                    <div className="text-sm font-medium">System Healthy</div>
                    <div className="text-xs text-muted-foreground">All services operational</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DashboardLayout>
    </ProtectedRoute>
  )
}

interface MetricCardProps {
  title: string
  value: string
  change?: string
  changeType: 'positive' | 'negative' | 'neutral'
  icon: string
}

function MetricCard({ title, value, change, changeType, icon }: MetricCardProps) {
  return (
    <div className="bg-card rounded-lg border border-border p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          {change && (
            <p className={`text-sm ${
              changeType === 'positive' ? 'text-success' : 
              changeType === 'negative' ? 'text-danger' : 'text-muted-foreground'
            }`}>
              {change} from last month
            </p>
          )}
        </div>
        <div className={`h-12 w-12 rounded-lg flex items-center justify-center ${
          changeType === 'positive' ? 'bg-success/10' : 
          changeType === 'negative' ? 'bg-danger/10' : 'bg-muted'
        }`}>
          {/* Icon placeholder */}
          <div className={`h-6 w-6 ${
            changeType === 'positive' ? 'text-success' : 
            changeType === 'negative' ? 'text-danger' : 'text-muted-foreground'
          }`}>
            📊
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatusItemProps {
  label: string
  status: 'healthy' | 'warning' | 'error'
}

function StatusItem({ label, status }: StatusItemProps) {
  const statusConfig = {
    healthy: { color: 'bg-success', text: 'Operational' },
    warning: { color: 'bg-warning', text: 'Degraded' },
    error: { color: 'bg-danger', text: 'Down' }
  }

  const config = statusConfig[status]

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center space-x-2">
        <div className={`h-2 w-2 rounded-full ${config.color}`} />
        <span className="text-sm font-medium">{config.text}</span>
      </div>
    </div>
  )
}