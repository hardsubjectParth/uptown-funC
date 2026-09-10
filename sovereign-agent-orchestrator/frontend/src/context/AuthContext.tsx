import { createContext, useContext, useMemo, useState } from 'react'
import { devLogin, type User } from '../services/api'

type AuthContextType = {
  token: string | null
  user: User | null
  isLoggedIn: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const SESSION_KEY = 'sovereign-dev-session'
const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<{ token: string; user: User } | null>(() => {
    const stored = sessionStorage.getItem(SESSION_KEY)
    return stored ? JSON.parse(stored) : null
  })

  const value = useMemo<AuthContextType>(() => ({
    token: session?.token ?? null,
    user: session?.user ?? null,
    isLoggedIn: Boolean(session),
    login: async (username, password) => {
      const result = await devLogin(username, password)
      const next = { token: result.access_token, user: result.user }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(next))
      setSession(next)
    },
    logout: () => { sessionStorage.removeItem(SESSION_KEY); setSession(null) },
  }), [session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
