import { createBrowserRouter, Navigate } from 'react-router-dom'
import { LoginPage } from '@/features/auth/ui/LoginPage'
import { RegisterPage } from '@/features/auth/ui/RegisterPage'
import { VerifyPage } from '@/features/auth/ui/VerifyPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { AppLayout } from '@/app/layout/AppLayout'
import { ThemePage } from '@/features/topic/ui/ThemePage'
import { SourcesPage } from '@/features/topic/ui/SourcesPage'
import { QuantaPage } from '@/features/quanta'
import { EntitiesPage } from '@/features/entity'
import { EventsPage } from '@/features/event/ui/EventsPage'
import { LandscapePage } from '@/features/landscape'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/topic/theme" replace />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/verify',
    element: <VerifyPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/topic/theme" replace />,
      },
      {
        path: 'topic',
        children: [
          {
            index: true,
            element: <Navigate to="/topic/theme" replace />,
          },
          {
            path: 'theme',
            element: <ThemePage />,
          },
          {
            path: 'sources',
            element: <SourcesPage />,
          },
          {
            path: 'quanta',
            element: <QuantaPage />,
          },
          {
            path: 'entities',
            element: <EntitiesPage />,
          },
          {
            path: 'events',
            element: <EventsPage />,
          },
          {
            path: 'landscape',
            element: <LandscapePage />,
          },
        ],
      },
    ],
  },
])
