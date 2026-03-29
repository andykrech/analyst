import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/features/auth/auth.store'
import { BillingUsageModal } from '@/features/billing'
import { useTopicStore } from '@/app/store/topicStore'
import './TopBar.css'

export function TopBar() {
  const email = useAuthStore((s) => s.email)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const activeTopicId = useTopicStore((s) => s.activeTopicId)
  const [isBillingOpen, setIsBillingOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="top-bar">
      <div className="top-bar__left">
        <button
          type="button"
          className="top-bar__action"
          onClick={() => setIsBillingOpen(true)}
          disabled={!activeTopicId}
          title={activeTopicId ? 'Открыть детальный биллинг' : 'Сначала выберите тему'}
        >
          Детальный биллинг
        </button>
      </div>
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

      <BillingUsageModal
        themeId={activeTopicId}
        isOpen={isBillingOpen}
        onClose={() => setIsBillingOpen(false)}
      />
    </header>
  )
}
