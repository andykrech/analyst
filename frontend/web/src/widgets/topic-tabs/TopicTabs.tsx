import { NavLink } from 'react-router-dom'
import { useTopicStore } from '@/app/store/topicStore'
import './TopicTabs.css'

export function TopicTabs() {
  const setActiveTab = useTopicStore((s) => s.setActiveTab)

  return (
    <nav className="topic-tabs" aria-label="Вкладки темы">
      <NavLink
        to="/topic/theme"
        className={({ isActive }) =>
          `topic-tabs__link ${isActive ? 'topic-tabs__link--active' : ''}`
        }
        onClick={() => setActiveTab('theme')}
      >
        Тема
      </NavLink>
      <NavLink
        to="/topic/sources"
        className={({ isActive }) =>
          `topic-tabs__link ${isActive ? 'topic-tabs__link--active' : ''}`
        }
        onClick={() => setActiveTab('sources')}
      >
        Источники
      </NavLink>
    </nav>
  )
}
