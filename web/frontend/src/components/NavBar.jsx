import { Link, useLocation, useNavigate } from 'react-router-dom'
import { createSession } from '../api'

export default function NavBar({ onSessionCreated }) {
  const location = useLocation()
  const navigate = useNavigate()

  const handleNew = async () => {
    try {
      const res = await createSession()
      navigate(`/chat/${res.data.session_id}`)
      if (onSessionCreated) onSessionCreated()
    } catch (err) {
      console.error('Failed to create session', err)
    }
  }

  const linkClass = (path) =>
    `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
      location.pathname.startsWith(path)
        ? 'bg-blue-50 text-blue-700'
        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    }`

  return (
    <header className="h-14 shrink-0 flex items-center px-6 bg-white border-b border-gray-200 z-10">
      <span className="text-blue-700 font-bold text-lg tracking-tight mr-8 select-none">
        OT Tutor
      </span>

      <nav className="flex gap-1 flex-1">
        <Link to="/chat" className={linkClass('/chat')}>Chat</Link>
        <Link to="/dashboard" className={linkClass('/dashboard')}>Dashboard</Link>
      </nav>

      <button
        onClick={handleNew}
        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-sm font-medium rounded-lg transition-colors"
      >
        + New Session
      </button>
    </header>
  )
}
