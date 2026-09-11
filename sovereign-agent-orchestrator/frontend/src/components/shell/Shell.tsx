import type { ReactNode } from 'react'
import ProtectedRoute from '../ProtectedRoute'
import Sidebar from './Sidebar'

function Shell({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden bg-background text-foreground">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </ProtectedRoute>
  )
}

export default Shell
