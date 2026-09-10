import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Login() {
  const { isLoggedIn, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (isLoggedIn) return <Navigate to="/dashboard" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/dashboard', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to sign in')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>Sovereign AI</h1>
        <p>Local development sign-in</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="username">Test account</label>
          <select id="username" value={username} onChange={(event) => setUsername(event.target.value)}>
            <option value="admin">Admin</option>
            <option value="higher">Higher employee</option>
            <option value="lower">Lower employee</option>
          </select>
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" />
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button type="submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p className="helper-text">Passwords are configured in the backend <code>.env</code>. This screen only works while <code>DEV_AUTH_ENABLED=true</code>.</p>
      </div>
    </main>
  )
}

export default Login
