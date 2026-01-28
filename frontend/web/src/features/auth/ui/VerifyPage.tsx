import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { authApi } from '../api/authApi'
import type { ApiError } from '@/shared/api/apiClient'
import './VerifyPage.css'

export function VerifyPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  
  const [loading, setLoading] = useState(true)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('Токен не предоставлен')
      setLoading(false)
      return
    }

    const verify = async () => {
      try {
        await authApi.verifyEmail(token)
        setSuccess(true)
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('Произошла ошибка при подтверждении email')
        }
      } finally {
        setLoading(false)
      }
    }

    verify()
  }, [token])

  if (loading) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>Подтверждение email</h1>
          <p>Проверка токена...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>Ошибка</h1>
          <div className="error-message">{error}</div>
          <Link to="/login" className="auth-link">
            Перейти к входу
          </Link>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>Email подтверждён</h1>
          <p>Ваш email успешно подтверждён. Теперь вы можете войти в систему.</p>
          <Link to="/login" className="auth-link">
            Перейти к входу
          </Link>
        </div>
      </div>
    )
  }

  return null
}
