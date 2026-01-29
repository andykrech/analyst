import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/auth.store'
import { setOnUnauthorized } from '@/shared/api/apiClient'

/**
 * Регистрирует обработчик 401 в apiClient.
 * При получении 401 выполняет logout и редирект на /login.
 * Подключается один раз на уровне layout или router.
 */
export function UnauthorizedBridge() {
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  useEffect(() => {
    setOnUnauthorized(() => {
      logout()
      navigate('/login')
    })
    return () => setOnUnauthorized(null)
  }, [logout, navigate])

  return null
}
