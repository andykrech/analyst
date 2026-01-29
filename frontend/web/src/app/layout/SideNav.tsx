import { NavLink } from 'react-router-dom'
import { NavigationRegistry } from '@/app/navigation'
import './SideNav.css'

export function SideNav() {
  const items = NavigationRegistry.getItems()

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
              end={item.path !== '/topics/new'}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
