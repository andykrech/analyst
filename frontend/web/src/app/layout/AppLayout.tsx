import { Outlet, useLocation } from 'react-router-dom'
import { SideNav } from './SideNav'
import { TopBar } from './TopBar'
import { TopicTabs } from '@/widgets/topic-tabs'
import { UnauthorizedBridge } from '@/app/UnauthorizedBridge'
import { useUnsavedChangesWarning } from '@/shared/lib/useUnsavedChangesWarning'
import './AppLayout.css'

export function AppLayout() {
  const location = useLocation()
  const showTopicTabs = location.pathname.startsWith('/topic')

  useUnsavedChangesWarning()

  return (
    <div className="app-layout">
      <aside className="app-layout__side">
        <SideNav />
      </aside>
      <div className="app-layout__main">
        <TopBar />
        {showTopicTabs && <TopicTabs />}
        <main className="app-layout__content">
          <UnauthorizedBridge />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
