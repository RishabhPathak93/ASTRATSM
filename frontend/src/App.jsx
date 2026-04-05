import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore.js'
import { Spinner } from '@/components/ui/index.jsx'

import AppLayout from '@/components/layout/AppLayout.jsx'
import LoginPage from '@/pages/Login.jsx'
import DashboardPage from '@/pages/Dashboard.jsx'
import ProjectsPage from '@/pages/Projects.jsx'
import ProjectDetailPage from '@/pages/ProjectDetail.jsx'
import ClientsPage from '@/pages/Clients.jsx'
import ClientDetailPage from '@/pages/ClientDetail.jsx'
import TimelinesPage from '@/pages/Timelines.jsx'
import ChatPage from '@/pages/Chat.jsx'
import ApprovalsPage from '@/pages/Approvals.jsx'
import { NotificationsPage, ResourcesPage, ProfilePage, SettingsPage } from '@/pages/Other.jsx'

function ProtectedRoute({ children }) {
  const isAuth = useAuthStore(s => s.isAuthenticated)
  return isAuth ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const isAuth = useAuthStore(s => s.isAuthenticated)
  return !isAuth ? children : <Navigate to="/dashboard" replace />
}

function PermissionRoute({ permission, children }) {
  const user = useAuthStore(s => s.user)
  const hasPermission = useAuthStore(s => s.hasPermission)
  if (!user) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={26} />
      </div>
    )
  }
  return hasPermission(permission) || hasPermission(`${permission}_view`)
    ? children
    : <Navigate to="/dashboard" replace />
}

function RoleRoute({ roles, children }) {
  const user = useAuthStore(s => s.user)
  if (!user) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={26} />
      </div>
    )
  }
  return roles.includes(user?.role) ? children : <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />

      <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="clients" element={<PermissionRoute permission="clients"><ClientsPage /></PermissionRoute>} />
        <Route path="clients/:id" element={<PermissionRoute permission="clients"><ClientDetailPage /></PermissionRoute>} />
        <Route path="projects" element={<PermissionRoute permission="projects"><ProjectsPage /></PermissionRoute>} />
        <Route path="projects/:id" element={<PermissionRoute permission="projects"><ProjectDetailPage /></PermissionRoute>} />
        <Route path="timelines" element={<PermissionRoute permission="timelines"><TimelinesPage /></PermissionRoute>} />
        <Route path="resources" element={<PermissionRoute permission="resources"><ResourcesPage /></PermissionRoute>} />
        <Route path="chat" element={<PermissionRoute permission="chat"><ChatPage /></PermissionRoute>} />
        <Route path="approvals" element={<RoleRoute roles={['admin', 'manager', 'resource']}><ApprovalsPage /></RoleRoute>} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="settings" element={<PermissionRoute permission="access_control"><SettingsPage /></PermissionRoute>} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
