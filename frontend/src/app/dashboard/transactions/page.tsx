'use client'

import React, { useState, useEffect } from 'react'
import { ProtectedRoute } from '@/hooks/useAuth'
import DashboardLayout from '@/components/DashboardLayout'
import { apiClient } from '@/lib/api-client'
import { Transaction } from '@/types'
import { formatCurrency, formatDate, formatPercentage } from '@/lib/utils'

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [filters, setFilters] = useState({
    search: '',
    riskLevel: 'all',
    status: 'all',
    dateFrom: '',
    dateTo: ''
  })

  const fetchTransactions = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: '20',
        ...(filters.search && { search: filters.search }),
        ...(filters.riskLevel !== 'all' && { risk: filters.riskLevel }),
        ...(filters.status !== 'all' && { status: filters.status }),
        ...(filters.dateFrom && { dateFrom: filters.dateFrom }),
        ...(filters.dateTo && { dateTo: filters.dateTo })
      })

      const response = await apiClient.getTransactions(params)
      setTransactions(response.transactions)
      setTotalPages(Math.ceil(response.total / 20))
    } catch (error: any) {
      setError(error.message || 'Failed to load transactions')
      console.error('Error fetching transactions:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions()
  }, [currentPage, filters])

  const getRiskBadge = (riskScore: number) => {
    if (riskScore >= 0.8) {
      return <span className="badge badge-danger">High Risk ({formatPercentage(riskScore)})</span>
    } else if (riskScore >= 0.5) {
      return <span className="badge badge-warning">Medium Risk ({formatPercentage(riskScore)})</span>
    } else {
      return <span className="badge badge-success">Low Risk ({formatPercentage(riskScore)})</span>
    }
  }

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      approved: { class: 'badge-success', label: 'Approved' },
      rejected: { class: 'badge-danger', label: 'Rejected' },
      pending: { class: 'badge-warning', label: 'Pending' },
      flagged: { class: 'badge-danger', label: 'Flagged' }
    }
    
    const config = statusConfig[status as keyof typeof statusConfig] || { class: 'badge-muted', label: status }
    
    return <span className={`badge ${config.class}`}>{config.label}</span>
  }

  const handleFilterChange = (field: string, value: string) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }))
    setCurrentPage(1)
  }

  if (loading && transactions.length === 0) {
    return (
      <ProtectedRoute>
        <DashboardLayout>
          <div className="flex items-center justify-center h-64">
            <div className="loading-spinner h-8 w-8" />
            <span className="ml-2 text-muted-foreground">Loading transactions...</span>
          </div>
        </DashboardLayout>
      </ProtectedRoute>
    )
  }

  return (
    <ProtectedRoute>
      <DashboardLayout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Transactions</h1>
              <p className="text-muted-foreground">Monitor and analyze transaction data</p>
            </div>
            <button className="btn-primary">
              Export Data
            </button>
          </div>

          {/* Filters */}
          <div className="bg-card rounded-lg border border-border p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div>
                <label className="form-label" htmlFor="search">Search</label>
                <input
                  id="search"
                  type="text"
                  className="form-input"
                  placeholder="Transaction ID, merchant..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                />
              </div>

              <div>
                <label className="form-label" htmlFor="riskLevel">Risk Level</label>
                <select
                  id="riskLevel"
                  className="form-input"
                  value={filters.riskLevel}
                  onChange={(e) => handleFilterChange('riskLevel', e.target.value)}
                >
                  <option value="all">All Levels</option>
                  <option value="high">High Risk</option>
                  <option value="medium">Medium Risk</option>
                  <option value="low">Low Risk</option>
                </select>
              </div>

              <div>
                <label className="form-label" htmlFor="status">Status</label>
                <select
                  id="status"
                  className="form-input"
                  value={filters.status}
                  onChange={(e) => handleFilterChange('status', e.target.value)}
                >
                  <option value="all">All Statuses</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="pending">Pending</option>
                  <option value="flagged">Flagged</option>
                </select>
              </div>

              <div>
                <label className="form-label" htmlFor="dateFrom">From Date</label>
                <input
                  id="dateFrom"
                  type="date"
                  className="form-input"
                  value={filters.dateFrom}
                  onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                />
              </div>

              <div>
                <label className="form-label" htmlFor="dateTo">To Date</label>
                <input
                  id="dateTo"
                  type="date"
                  className="form-input"
                  value={filters.dateTo}
                  onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Error State */}
          {error && (
            <div className="bg-danger/10 border border-danger text-danger rounded-lg p-4">
              <div className="flex items-center">
                <span className="mr-2">⚠️</span>
                <span>{error}</span>
                <button 
                  onClick={() => fetchTransactions()}
                  className="ml-auto btn-outline btn-sm"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {/* Transactions Table */}
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="table-container">
              <table className="table-base">
                <thead className="table-header">
                  <tr>
                    <th className="table-header-cell">Transaction ID</th>
                    <th className="table-header-cell">Date</th>
                    <th className="table-header-cell">Amount</th>
                    <th className="table-header-cell">Merchant</th>
                    <th className="table-header-cell">Risk Score</th>
                    <th className="table-header-cell">Status</th>
                    <th className="table-header-cell">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id} className="table-row">
                      <td className="table-cell">
                        <span className="font-mono text-xs">{transaction.id}</span>
                      </td>
                      <td className="table-cell">
                        {formatDate(transaction.timestamp)}
                      </td>
                      <td className="table-cell font-medium">
                        {formatCurrency(transaction.amount)}
                      </td>
                      <td className="table-cell">
                        {transaction.merchant || 'Unknown'}
                      </td>
                      <td className="table-cell">
                        {getRiskBadge(transaction.riskScore)}
                      </td>
                      <td className="table-cell">
                        {getStatusBadge(transaction.status)}
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center space-x-2">
                          <button className="btn-ghost btn-sm">
                            View Details
                          </button>
                          {transaction.status === 'pending' && (
                            <>
                              <button className="btn-success btn-sm">
                                Approve
                              </button>
                              <button className="btn-danger btn-sm">
                                Reject
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Empty State */}
            {!loading && transactions.length === 0 && (
              <div className="text-center py-12">
                <div className="text-muted-foreground mb-4">📊 No transactions found</div>
                <p className="text-muted-foreground">
                  {Object.values(filters).some(f => f && f !== 'all') 
                    ? 'Try adjusting your filters'
                    : 'No transaction data available'
                  }
                </p>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-border">
                <div className="text-sm text-muted-foreground">
                  Showing {((currentPage - 1) * 20) + 1} to {Math.min(currentPage * 20, transactions.length)} of {transactions.length} results
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="btn-outline btn-sm"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1 text-sm">
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    className="btn-outline btn-sm"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {/* Loading Overlay */}
            {loading && transactions.length > 0 && (
              <div className="absolute inset-0 bg-background/80 flex items-center justify-center">
                <div className="loading-spinner h-6 w-6" />
                <span className="ml-2 text-muted-foreground">Updating...</span>
              </div>
            )}
          </div>
        </div>
      </DashboardLayout>
    </ProtectedRoute>
  )
}