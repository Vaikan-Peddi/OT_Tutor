import { useState } from 'react'
import { Link } from 'react-router-dom'

const PHASE_LABEL = {
  tutoring:   'Hints',
  reveal:     'Reveal',
  assessment: 'Clinical',
  mastery:    'Mastery',
}

const PHASE_COLOR = {
  tutoring:   'text-amber-600  bg-amber-50',
  reveal:     'text-ub-blue    bg-blue-50',
  assessment: 'text-purple-600 bg-purple-50',
  mastery:    'text-ub-gold-dk bg-ub-gold/10',
}

function PhaseChip({ phase }) {
  const label = PHASE_LABEL[phase] || phase
  const color = PHASE_COLOR[phase] || 'text-gray-500 bg-gray-100'
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide shrink-0 ${color}`}>
      {label}
    </span>
  )
}

export default function SessionSidebar({ sessions, activeSessionId }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside className={`shrink-0 flex flex-col h-full bg-white border-r border-gray-200 transition-all duration-300 ${collapsed ? 'w-12' : 'w-64'}`}>

      {collapsed ? (
        /* ── Collapsed strip ── */
        <div className="flex flex-col items-center py-3 gap-3">
          <button
            onClick={() => setCollapsed(false)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            title="Expand sidebar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
          <div className="flex flex-col gap-2 mt-1">
            {sessions.slice(0, 8).map((s) => (
              <Link
                key={s.id}
                to={`/chat/${s.id}`}
                title={s.topic_label || s.question || 'Session'}
                className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold transition-colors ${
                  s.id === activeSessionId
                    ? 'bg-ub-blue text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {(s.topic_label || s.question || '?')[0].toUpperCase()}
              </Link>
            ))}
          </div>
        </div>
      ) : (
        /* ── Expanded ── */
        <>
          <div className="px-4 py-3.5 border-b border-gray-100 flex items-center justify-between">
            <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">
              Sessions
            </p>
            <button
              onClick={() => setCollapsed(true)}
              className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              title="Collapse sidebar"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin py-1">
            {sessions.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <p className="text-gray-400 text-sm leading-relaxed">
                  No sessions yet.
                  <br />
                  <span className="text-ub-blue font-medium">+ New Session</span> to begin.
                </p>
              </div>
            ) : (
              sessions.map((s) => (
                <Link
                  key={s.id}
                  to={`/chat/${s.id}`}
                  className={`group block px-4 py-3 transition-colors border-l-2 ${
                    s.id === activeSessionId
                      ? 'border-ub-blue bg-ub-blue/5'
                      : 'border-transparent hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-0.5">
                    <p className={`text-sm leading-snug line-clamp-2 flex-1 ${
                      s.id === activeSessionId ? 'text-gray-900 font-medium' : 'text-gray-700'
                    }`}>
                      {s.topic_label || s.question || 'New session'}
                    </p>
                    <PhaseChip phase={s.phase} />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-gray-400 text-xs">Turn {s.turn_count}</span>
                    {s.avg_score != null ? (
                      <span className="text-ub-blue text-xs font-medium">· {s.avg_score}/100</span>
                    ) : s.mastery_done ? null : (
                      <span className="text-gray-300 text-xs">· in progress</span>
                    )}
                    {s.mastery_done && (
                      <span className="text-ub-gold font-bold text-xs ml-auto">✓</span>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </>
      )}
    </aside>
  )
}
