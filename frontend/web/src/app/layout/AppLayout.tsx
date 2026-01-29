import { Outlet } from 'react-router-dom'
import { SideNav } from './SideNav'
import { TopBar } from './TopBar'
import { UnauthorizedBridge } from '@/app/UnauthorizedBridge'
import './AppLayout.css'

export function AppLayout() {
  return (
    <div className="app-layout">
      <aside className="app-layout__side">
        <SideNav />
      </aside>
      <div className="app-layout__main">
        <TopBar />
        <main className="app-layout__content">
          <UnauthorizedBridge />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
