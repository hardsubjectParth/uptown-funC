import { useAuth } from '../context/AuthContext'

function Login() {
    const { isLoggedIn, login } = useAuth()
    return (
        <main className="login-page">
            <div className="login-card">
                <h1>Sovereign AI</h1>
                <p>Sovereign Agent Orchestrator</p>
                <p>Logged in: {isLoggedIn ? 'Yes' : 'No'}</p>
                <form
                    onSubmit={(event) => {
                        event.preventDefault()
                        login()
                    }}
                >
                    <label htmlFor="username">Username</label>
                    <input
                        id="username"
                        type="text"
                        placeholder="Enter your username"
                    />

                    <label htmlFor="password">Password</label>
                    <input
                        id="password"
                        type="password"
                        placeholder="Enter your password"
                    />

                    <button type="submit">Login</button>
                </form>
            </div>
        </main>
    )
}

export default Login