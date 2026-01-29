import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/auth.store'
import './TopBar.css'

export function TopBar() {
  const email = useAuthStore((s) => s.email)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="top-bar">
      <div className="top-bar__spacer" />
      <div className="top-bar__user">
        {email && <span className="top-bar__email">{email}</span>}
        <button
          type="button"
          className="top-bar__logout"
          onClick={handleLogout}
          aria-label="Выход"
        >
          Выход
        </button>
      </div>
    </header>
  )
}
