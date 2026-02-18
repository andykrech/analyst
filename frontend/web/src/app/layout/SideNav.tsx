import { useMemo } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { NavigationRegistry } from '@/app/navigation'
import type { NavItem } from '@/app/navigation'
import { useTopicStore } from '@/app/store/topicStore'
import { themesApi } from '@/features/topic/api/themesApi'
import { useThemes } from '@/features/topic/api/useThemes'
import './SideNav.css'

const SECTION_TITLES: Record<string, string> = {
  themes: 'Темы',
  reports: 'Отчёты',
  admin: 'Администрирование',
}

function groupBySection(items: NavItem[]): Map<string, NavItem[]> {
  const map = new Map<string, NavItem[]>()
  for (const item of items) {
    const sectionId = item.sectionId ?? 'main'
    if (!map.has(sectionId)) map.set(sectionId, [])
    map.get(sectionId)!.push(item)
  }
  return map
}

export function SideNav() {
  const items = NavigationRegistry.getItems()
  const location = useLocation()
  const navigate = useNavigate()
  const status = useTopicStore((s) => s.status)
  const activeTopicId = useTopicStore((s) => s.activeTopicId)
  const resetToEmptyDraft = useTopicStore((s) => s.resetToEmptyDraft)
  const loadThemeFromApi = useTopicStore((s) => s.loadThemeFromApi)
  const { loading: themesLoading } = useThemes()

  const sections = useMemo(() => groupBySection(items), [items])

  const handleNavClick = (
    e: React.MouseEvent<HTMLAnchorElement>,
    item: NavItem
  ) => {
    const pathname = location.pathname
    if (!pathname.startsWith('/topic')) return
    if (!item.path) return

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

  const handleThemeClick = async (themeId: string) => {
    const pathname = location.pathname
    if (!pathname.startsWith('/topic')) return
    if (themeId === activeTopicId) {
      navigate('/topic/theme')
      return
    }
    if (status === 'dirty') {
      if (!window.confirm('Есть несохранённые изменения. Перейти без сохранения?')) {
        return
      }
    }
    try {
      const response = await themesApi.getTheme(themeId, { skip401Redirect: true })
      loadThemeFromApi(response)
      navigate('/topic/theme')
    } catch {
      // ошибка загрузки — оставляем как есть
    }
  }

  return (
    <nav className="side-nav" aria-label="Основная навигация">
      {Array.from(sections.entries()).map(([sectionId, sectionItems]) => (
        <div key={sectionId} className="side-nav__section">
          <h2 className="side-nav__title">
            {SECTION_TITLES[sectionId] ?? sectionId}
          </h2>
          <ul className="side-nav__list">
            {sectionItems.map((item) => (
              <li key={item.key} className="side-nav__item">
                {item.path != null ? (
                  <NavLink
                    to={item.path}
                    className={({ isActive }) => {
                      const active =
                        item.key === 'new-topic'
                          ? location.pathname === '/topic/theme' && activeTopicId === null
                          : isActive
                      return `side-nav__link ${active ? 'side-nav__link--active' : ''}`
                    }}
                    end={item.path === '/topic/theme'}
                    onClick={(e) => handleNavClick(e, item)}
                  >
                    {item.label}
                  </NavLink>
                ) : item.themeId != null ? (
                  <button
                    type="button"
                    className={`side-nav__link side-nav__link--btn ${
                      activeTopicId === item.themeId ? 'side-nav__link--active' : ''
                    }`}
                    onClick={() => handleThemeClick(item.themeId!)}
                  >
                    {item.label}
                  </button>
                ) : null}
              </li>
            ))}
            {sectionId === 'themes' && themesLoading && (
              <li className="side-nav__item side-nav__item--muted">
                Загрузка…
              </li>
            )}
          </ul>
        </div>
      ))}
    </nav>
  )
}
