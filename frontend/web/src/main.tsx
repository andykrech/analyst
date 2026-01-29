import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './app/App.tsx'
import { useAuthStore } from '@/features/auth/auth.store'
import { setAuthTokenGetter } from '@/shared/api/apiClient'
import { NavigationRegistry, staticNavProvider } from '@/app/navigation'

setAuthTokenGetter(() => useAuthStore.getState().accessToken)
NavigationRegistry.register(staticNavProvider)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
