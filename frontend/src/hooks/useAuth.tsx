'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api-client'
import { AuthContext, User, LoginCredentials } from '@/types'
import toast from 'react-hot-toast'

const AuthContextInstance = createContext<AuthContext | undefined>(undefined)

interface AuthProviderProps {
  children: React.ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  // Check if user is authenticated and fetch user data
  const checkAuth = useCallback(async () => {
    try {
      if (apiClient.isAuthenticated()) {
        const userData = await apiClient.getCurrentUser()
        setUser(userData)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Login function
  const login = useCallback(async (credentials: LoginCredentials) => {
    try {
      setLoading(true)
      const { user: userData } = await apiClient.login(credentials)
      setUser(userData)
      toast.success('Login successful')
      router.push('/dashboard')
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.message || 'Login failed'
      toast.error(message)
      throw error
    } finally {
      setLoading(false)
    }
  }, [router])

  // Logout function
  const logout = useCallback(async () => {
    try {
      await apiClient.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      setUser(null)
      toast.success('Logged out successfully')
      router.push('/login')
    }
  }, [router])

  // Refresh token function
  const refreshToken = useCallback(async () => {
    try {
      await apiClient.refreshToken()
      // Optionally refetch user data
      await checkAuth()
    } catch (error) {
      console.error('Token refresh failed:', error)
      setUser(null)
      router.push('/login')
    }
  }, [checkAuth, router])

  // Initialize auth state
  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const value: AuthContext = {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    logout,
    refreshToken,
  }

  return (
    <AuthContextInstance.Provider value={value}>
      {children}
    </AuthContextInstance.Provider>
  )
}

// Hook to use auth context
export function useAuth(): AuthContext {
  const context = useContext(AuthContextInstance)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// HOC for protected routes
export function withAuth<P extends object>(Component: React.ComponentType<P>) {
  return function AuthenticatedComponent(props: P) {
    const { isAuthenticated, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
      if (!loading && !isAuthenticated) {
        router.push('/login')
      }
    }, [isAuthenticated, loading, router])

    if (loading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="loading-spinner h-8 w-8" />
          <span className="ml-2 text-muted-foreground">Loading...</span>
        </div>
      )
    }

    if (!isAuthenticated) {
      return null
    }

    return <Component {...props} />
  }
}

// HOC for role-based access control
export function withRole<P extends object>(
  Component: React.ComponentType<P>,
  allowedRoles: string[]
) {
  return function RoleBasedComponent(props: P) {
    const { user, isAuthenticated, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
      if (!loading && !isAuthenticated) {
        router.push('/login')
      } else if (!loading && isAuthenticated && user && !allowedRoles.includes(user.role)) {
        toast.error('You do not have permission to access this page')
        router.push('/dashboard')
      }
    }, [isAuthenticated, loading, user, router])

    if (loading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="loading-spinner h-8 w-8" />
          <span className="ml-2 text-muted-foreground">Loading...</span>
        </div>
      )
    }

    if (!isAuthenticated || !user || !allowedRoles.includes(user.role)) {
      return null
    }

    return <Component {...props} />
  }
}

// Component for protecting routes
interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: string[]
  fallback?: React.ReactNode
}

export function ProtectedRoute({ 
  children, 
  allowedRoles,
  fallback
}: ProtectedRouteProps) {
  const { user, isAuthenticated, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login')
    } else if (
      !loading && 
      isAuthenticated && 
      user && 
      allowedRoles && 
      !allowedRoles.includes(user.role)
    ) {
      toast.error('You do not have permission to access this resource')
      router.push('/dashboard')
    }
  }, [isAuthenticated, loading, user, allowedRoles, router])

  if (loading) {
    return (
      fallback || (
        <div className="flex items-center justify-center min-h-screen">
          <div className="loading-spinner h-8 w-8" />
          <span className="ml-2 text-muted-foreground">Loading...</span>
        </div>
      )
    )
  }

  if (!isAuthenticated) {
    return null
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return null
  }

  return <>{children}</>
}