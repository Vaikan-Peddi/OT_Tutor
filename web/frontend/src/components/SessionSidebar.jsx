import { Link } from 'react-router-dom'

const PHASE_STYLES = {
  tutoring:   'bg-amber-500/20 text-amber-300',
  reveal:     'bg-blue-500/20 text-blue-300',
  assessment: 'bg-purple-500/20 text-purple-300',
  mastery:    'bg-green-500/20 text-green-300',
}

function PhaseChip({ phase }) {
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide ${PHASE_STYLES[phase] || 'bg-gray-500/20 text-gray-400'}`}>
      {phase}
    </span>
  )
}

export default function SessionSidebar({ sessions, activeSessionId }) {
  return (
    <aside className="w-60 shrink-0 flex flex-col h-full bg-gray-900 border-r border-gray-800">
      <div className="px-4 py-3 border-b border-gray-800">
        <p className="text-gray-500 text-[11px] font-semibold uppercase tracking-widest">
          Sessions
        </p>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin py-1">
        {sessions.length === 0 ? (
          <p className="text-gray-600 text-sm px-4 py-8 text-center leading-relaxed">
            No sessions yet.{' '}
            <br />
            Click <strong className="text-gray-400">+ New Session</strong> to begin.
          </p>
        ) : (
          sessions.map((s) => (
            <Link
              key={s.id}
              to={`/chat/${s.id}`}
              className={`block px-4 py-3 border-l-2 transition-colors ${
                s.id === activeSessionId
                  ? 'border-blue-500 bg-gray-800'
                  : 'border-transparent hover:bg-gray-800/60'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-gray-200 text-sm leading-tight line-clamp-2 flex-1">
                  {s.topic_label || s.question || 'New session'}
                </p>
                <PhaseChip phase={s.phase} />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-gray-600 text-xs">Turn {s.turn_count}</span>
                {s.avg_score != null && (
                  <span className="text-gray-600 text-xs">· {s.avg_score}/100</span>
                )}
                {s.mastery_done && (
                  <span className="text-green-500 text-xs ml-auto">✓</span>
                )}
              </div>
            </Link>
          ))
        )}
      </div>
    </aside>
  )
}
