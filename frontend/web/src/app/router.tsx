import { createBrowserRouter, Navigate } from 'react-router-dom'
import { LoginPage } from '@/features/auth/ui/LoginPage'
import { RegisterPage } from '@/features/auth/ui/RegisterPage'
import { VerifyPage } from '@/features/auth/ui/VerifyPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { AppLayout } from '@/app/layout/AppLayout'
import { NewTopicPage } from '@/features/topics/ui/NewTopicPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/topics/new" replace />,
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
        element: <Navigate to="/topics/new" replace />,
      },
      {
        path: 'topics/new',
        element: <NewTopicPage />,
      },
    ],
  },
])
