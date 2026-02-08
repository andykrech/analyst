import { createBrowserRouter, Navigate } from 'react-router-dom'
import { LoginPage } from '@/features/auth/ui/LoginPage'
import { RegisterPage } from '@/features/auth/ui/RegisterPage'
import { VerifyPage } from '@/features/auth/ui/VerifyPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { AppLayout } from '@/app/layout/AppLayout'
import { ThemePage } from '@/features/topic/ui/ThemePage'
import { SourcesPage } from '@/features/topic/ui/SourcesPage'

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
        ],
      },
    ],
  },
])
