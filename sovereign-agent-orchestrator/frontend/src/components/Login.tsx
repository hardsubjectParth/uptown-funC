import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'

// The backend's dev-login only recognizes three fixed accounts (admin/higher/lower --
// app/dev_auth.py), not an arbitrary email. A free-text "protocol identifier" field
// per the rebuild spec would just fail against the real auth -- kept the console
// styling, swapped the input for the same role selector the working login already used.
const ACCOUNTS = [
  { value: 'admin', label: 'admin@sovereign.io' },
  { value: 'higher', label: 'higher@sovereign.io' },
  { value: 'lower', label: 'lower@sovereign.io' },
]

function Login() {
  const { isLoggedIn, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [unlocking, setUnlocking] = useState(false)

  if (isLoggedIn && !unlocking) return <Navigate to="/app/feed" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      setUnlocking(true)
      window.setTimeout(() => navigate('/app/feed', { replace: true }), 220)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to sign in')
      setSubmitting(false)
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: 'radial-gradient(ellipse at center, rgba(76,141,255,0.08), transparent 60%)' }}
      />

      <motion.div
        animate={unlocking ? { scale: 0.98, opacity: 0 } : { scale: 1, opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="border-hairline relative w-full max-w-sm rounded-none bg-surface p-8"
      >
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Sovereign AI</h1>
          <p className="label-micro mt-1">Intelligence Protocol Access</p>
        </div>

        <div className="mt-6 flex items-center justify-between border-t border-b border-white/8 py-2.5">
          <span className="label-micro">Sovereign OS v4.2.0</span>
          <span className="label-micro flex items-center gap-1.5 text-accent">
            <span className="h-1.5 w-1.5 animate-status-pulse rounded-full bg-accent" style={{ boxShadow: '0 0 6px var(--color-accent)' }} />
            Secure Connection Active
          </span>
        </div>

        <h2 className="mt-6 text-base font-medium text-foreground">Authorization Required</h2>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-2">
            <span className="label-micro">Protocol Identifier</span>
            <select
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="border-hairline bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-accent"
            >
              {ACCOUNTS.map((account) => <option value={account.value} key={account.value}>{account.label}</option>)}
            </select>
          </label>

          <label className="flex flex-col gap-2">
            <span className="label-micro">Access Token</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              className="border-hairline bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-accent"
              style={{ letterSpacing: password ? '0.2em' : 'normal' }}
            />
          </label>

          {error ? <p className="text-xs text-danger" role="alert">{error}</p> : null}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition hover:shadow-[0_0_16px_rgba(76,141,255,0.4)] disabled:opacity-60"
          >
            {submitting ? 'Initializing…' : 'Initialize Session'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">New agent? Request Access Protocol</p>
      </motion.div>
    </main>
  )
}

export default Login
