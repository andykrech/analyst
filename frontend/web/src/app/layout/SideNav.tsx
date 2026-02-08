import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { NavigationRegistry } from '@/app/navigation'
import { useTopicStore } from '@/app/store/topicStore'
import './SideNav.css'

export function SideNav() {
  const items = NavigationRegistry.getItems()
  const location = useLocation()
  const navigate = useNavigate()
  const status = useTopicStore((s) => s.status)
  const resetToEmptyDraft = useTopicStore((s) => s.resetToEmptyDraft)

  const handleNavClick = (
    e: React.MouseEvent<HTMLAnchorElement>,
    item: { key: string; path: string }
  ) => {
    const pathname = location.pathname
    if (!pathname.startsWith('/topic')) return

    if (status === 'dirty') {
      e.preventDefault()
      if (!window.confirm('Есть несохранённые изменения. Перейти без сохранения?')) {
        return
      }
      if (item.key === 'new-topic') resetToEmptyDraft()
      navigate(item.path)
    } else if (item.key === 'new-topic') {
      e.preventDefault()
      resetToEmptyDraft()
      navigate(item.path)
    }
  }

  return (
    <nav className="side-nav" aria-label="Основная навигация">
      <ul className="side-nav__list">
        {items.map((item) => (
          <li key={item.key} className="side-nav__item">
            <NavLink
              to={item.path}
              className={({ isActive }) =>
                `side-nav__link ${isActive ? 'side-nav__link--active' : ''}`
              }
              end={item.path === '/topic/theme'}
              onClick={(e) => handleNavClick(e, item)}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
