import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useTopicStore } from '@/app/store/topicStore'
import { authApi } from './api/authApi'
import { useAuthStore } from './auth.store'
import { uiStateApi } from '@/features/user/api/uiStateApi'
import { themesApi } from '@/features/topic/api/themesApi'
import { ApiError } from '@/shared/api/apiClient'
import './ProtectedRoute.css'

const DEFAULT_TOPIC_URL = '/topic/theme'
const TOPIC_URLS = ['/topic/theme', '/topic/sources'] as const

function isValidTopicUrl(url: string): url is (typeof TOPIC_URLS)[number] {
  return TOPIC_URLS.includes(url as (typeof TOPIC_URLS)[number])
}

interface ProtectedRouteProps {
  children: React.ReactNode
}

type ValidationStatus = 'pending' | 'valid' | 'invalid'

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const accessToken = useAuthStore((s) => s.accessToken)
  const logout = useAuthStore((s) => s.logout)
  const [status, setStatus] = useState<ValidationStatus>('pending')
  const [uiStateReady, setUiStateReady] = useState(false)
  const initialLoadDoneRef = useRef(false)

  useEffect(() => {
    if (!accessToken) {
      initialLoadDoneRef.current = false
      setUiStateReady(false)
      setStatus('invalid')
      return
    }
    let cancelled = false
    authApi
      .me({ skip401Redirect: true })
      .then(() => {
        if (!cancelled) setStatus('valid')
      })
      .catch((e) => {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 401) {
          logout()
          setStatus('invalid')
          navigate('/login', { replace: true, state: { from: location } })
        } else {
          setStatus('valid')
        }
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, logout, location, navigate])

  useEffect(() => {
    if (status !== 'valid') return
    if (initialLoadDoneRef.current) {
      setUiStateReady(true)
      return
    }
    initialLoadDoneRef.current = true

    const loadUiState = async () => {
      const resetToDefault = () => {
        useTopicStore.getState().resetToEmptyDraft()
        useTopicStore.getState().setActiveTab('theme')
        if (location.pathname !== DEFAULT_TOPIC_URL) {
          navigate(DEFAULT_TOPIC_URL, { replace: true })
        }
      }

      try {
        const { state } = await uiStateApi.getState({ skip401Redirect: true })
        const themeId = state?.active_theme_id
        const savedUrl = state?.url

        if (themeId && typeof themeId === 'string') {
          try {
            const themeResponse = await themesApi.getTheme(themeId, {
              skip401Redirect: true,
            })
            useTopicStore.getState().loadThemeFromApi(themeResponse)
            const url =
              savedUrl && isValidTopicUrl(savedUrl) ? savedUrl : DEFAULT_TOPIC_URL
            useTopicStore.getState().setActiveTab(
              url === '/topic/sources' ? 'sources' : 'theme'
            )
            if (location.pathname !== url) {
              navigate(url, { replace: true })
            }
          } catch {
            resetToDefault()
          }
        } else {
          resetToDefault()
        }
      } catch {
        resetToDefault()
      }
    }

    loadUiState().finally(() => setUiStateReady(true))
  }, [status, navigate, location.pathname])

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (status === 'pending') {
    return (
      <div className="protected-route__loading" aria-label="Проверка авторизации">
        Проверка авторизации…
      </div>
    )
  }

  if (status === 'invalid') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!uiStateReady) {
    return (
      <div className="protected-route__loading" aria-label="Загрузка приложения">
        Загрузка…
      </div>
    )
  }

  return <>{children}</>
}
