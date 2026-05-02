import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { createSession } from '../api'

export default function NavBar({ onSessionCreated }) {
  const location  = useLocation()
  const navigate  = useNavigate()
  const [error,    setError]    = useState(null)
  const [creating, setCreating] = useState(false)

  const handleNew = async () => {
    setError(null)
    setCreating(true)
    try {
      const res = await createSession()
      navigate(`/chat/${res.data.session_id}`)
      if (onSessionCreated) onSessionCreated()
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to start session. Is the server running?'
      setError(detail)
    } finally {
      setCreating(false)
    }
  }

  const linkClass = (path) =>
    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
      location.pathname.startsWith(path)
        ? 'bg-white/20 text-white'
        : 'text-blue-100 hover:text-white hover:bg-white/10'
    }`

  return (
    <header className="shrink-0 bg-ub-blue z-10 shadow-md">
      <div className="h-14 flex items-center gap-6 px-5">
        {/* Logo — inverted to white for the blue navbar */}
        <img
          src="/ub-logo.png"
          alt="University at Buffalo"
          className="h-8 w-auto"
          style={{ filter: 'brightness(0) invert(1)' }}
        />

        <div className="h-6 w-px bg-white/20" />

        <nav className="flex gap-1">
          <Link to="/chat"      className={linkClass('/chat')}>Chat</Link>
          <Link to="/dashboard" className={linkClass('/dashboard')}>Dashboard</Link>
        </nav>

        <div className="flex-1" />

        <button
          onClick={handleNew}
          disabled={creating}
          className="flex items-center gap-1.5 px-4 py-1.5 bg-white/15 hover:bg-white/25 border border-white/30 hover:border-white/50 disabled:opacity-60 disabled:cursor-wait text-white text-sm font-semibold rounded-lg transition-colors"
        >
          {creating ? (
            'Starting…'
          ) : (
            <>
              <span className="text-base leading-none">+</span>
              New Session
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="flex items-center justify-between bg-red-900/80 border-t border-red-700 px-5 py-2">
          <p className="text-white text-sm">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-red-300 hover:text-white text-lg leading-none ml-4"
          >×</button>
        </div>
      )}
    </header>
  )
}
