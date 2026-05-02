import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'

const PHASE_META = {
  tutoring:   { label: 'Socratic Hints',      color: 'bg-amber-50   text-amber-700   border border-amber-200' },
  reveal:     { label: 'Answer Revealed',     color: 'bg-blue-50    text-ub-blue     border border-blue-200'  },
  assessment: { label: 'Clinical Assessment', color: 'bg-purple-50  text-purple-700  border border-purple-200'},
  mastery:    { label: 'Mastery Complete',    color: 'bg-ub-gold/10 text-ub-gold-dk  border border-ub-gold/30'},
}


function PhaseIndicator({ phase }) {
  const { label, color } = PHASE_META[phase] || { label: phase, color: 'bg-gray-100 text-gray-500 border border-gray-200' }
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${color}`}>{label}</span>
  )
}


function TypingDots() {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-ub-blue flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" xmlns="http://www.w3.org/2000/svg">
          <line x1="10" y1="2" x2="10" y2="5" stroke="#FFB81C" strokeWidth="1.5" strokeLinecap="round"/>
          <circle cx="10" cy="1.5" r="1" fill="#FFB81C"/>
          <rect x="4" y="5" width="12" height="9" rx="2.5" fill="white" fillOpacity="0.92"/>
          <circle cx="7.5" cy="9" r="1.4" fill="#005BBB"/>
          <circle cx="12.5" cy="9" r="1.4" fill="#005BBB"/>
          <circle cx="7.9" cy="8.6" r="0.45" fill="white"/>
          <circle cx="12.9" cy="8.6" r="0.45" fill="white"/>
          <rect x="7" y="11.5" width="6" height="1" rx="0.5" fill="#005BBB" fillOpacity="0.5"/>
          <rect x="2.5" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
          <rect x="16" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
          <rect x="6" y="14.5" width="8" height="4" rx="1.5" fill="white" fillOpacity="0.7"/>
          <rect x="8.25" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
          <rect x="10.55" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
        </svg>
      </div>
      <div className="pt-2">
        <div className="flex gap-1 items-center">
          {[0, 160, 320].map((delay) => (
            <span
              key={delay}
              className="w-2 h-2 bg-gray-300 rounded-full animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export default function ChatWindow({
  sessionId,
  sessionState,
  messages,
  loading,
  masteryLoading,
  onSend,
  onMastery,
}) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── Empty state ───────────────────────────────────────────────────────
  if (!sessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-white">
        <img src="/ub-logo.png" alt="University at Buffalo" className="h-12 mb-6 opacity-90" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">OT Tutor</h2>
        <p className="text-gray-400 text-sm text-center max-w-xs leading-relaxed">
          A Socratic tutor for Occupational Therapy students at the University at Buffalo.
        </p>
        <p className="text-gray-400 text-sm mt-4">
          Press <span className="font-semibold text-ub-blue">+ New Session</span> to begin.
        </p>
      </div>
    )
  }

  const masteryAvailable = sessionState?.mastery_unlocked && !sessionState?.mastery_done
  const isDone           = sessionState?.mastery_done

  return (
    <div className="flex-1 flex flex-col h-full bg-white overflow-hidden">

      {/* Session header */}
      <div className="shrink-0 flex items-center justify-between px-6 py-2.5 border-b border-gray-100 bg-white">
        <p className="text-sm font-medium text-gray-700 truncate max-w-md">
          {sessionState?.topic_label || sessionState?.question || `Session ${sessionId}`}
          {sessionState?.image_identified_as && (
            <span className="text-gray-400 font-normal ml-1.5">· {sessionState.image_identified_as}</span>
          )}
        </p>
        <div className="flex items-center gap-2 shrink-0">
          {sessionState?.phase && <PhaseIndicator phase={sessionState.phase} />}
          <span className="text-xs text-gray-400 tabular-nums">Turn {sessionState?.turn_count ?? 0}</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin bg-white">
        <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
          {messages.map((msg, i) => (
            <MessageBubble key={msg.id ?? i} message={msg} />
          ))}
          {loading && <TypingDots />}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 bg-white border-t border-gray-100 px-4 pt-3 pb-4">

        {isDone ? (
          /* ── Session complete — input locked ── */
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-4 px-5 py-4 bg-gradient-to-r from-ub-blue/5 to-ub-gold/5 border border-ub-gold/25 rounded-2xl">
              <div className="w-10 h-10 rounded-full bg-ub-blue flex items-center justify-center shrink-0 shadow-sm">
                <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5" xmlns="http://www.w3.org/2000/svg">
                  <line x1="10" y1="2" x2="10" y2="5" stroke="#FFB81C" strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="10" cy="1.5" r="1" fill="#FFB81C"/>
                  <rect x="4" y="5" width="12" height="9" rx="2.5" fill="white" fillOpacity="0.92"/>
                  <circle cx="7.5" cy="9" r="1.4" fill="#005BBB"/>
                  <circle cx="12.5" cy="9" r="1.4" fill="#005BBB"/>
                  <circle cx="7.9" cy="8.6" r="0.45" fill="white"/>
                  <circle cx="12.9" cy="8.6" r="0.45" fill="white"/>
                  <rect x="7" y="11.5" width="6" height="1" rx="0.5" fill="#005BBB" fillOpacity="0.5"/>
                  <rect x="2.5" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
                  <rect x="16" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
                  <rect x="6" y="14.5" width="8" height="4" rx="1.5" fill="white" fillOpacity="0.7"/>
                  <rect x="8.25" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
                  <rect x="10.55" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-800">Session Complete 🎓</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {sessionState?.avg_score != null
                    ? `Final score: ${sessionState.avg_score}/100 · `
                    : ''}
                  Start a new session to keep studying.
                </p>
              </div>
              <span className="text-ub-gold font-bold text-lg shrink-0">✓</span>
            </div>
          </div>
        ) : (
          /* ── Normal input ── */
          <>
            {(masteryAvailable || isDone) && (
              <div className="max-w-2xl mx-auto mb-2 flex justify-end">
                <button
                  onClick={masteryAvailable ? onMastery : undefined}
                  disabled={masteryLoading}
                  className="px-4 py-1.5 text-sm font-semibold rounded-lg transition-colors bg-ub-gold hover:bg-ub-gold-dk text-ub-navy shadow-sm"
                >
                  {masteryLoading ? 'Generating…' : '✦ Mastery Summary'}
                </button>
              </div>
            )}

            {!masteryAvailable && !isDone && sessionState?.turn_count != null && (
              <p className="max-w-2xl mx-auto text-xs text-gray-400 mb-2 text-right">
                {Math.max(0, 4 - (sessionState.turn_count || 0)) > 0
                  ? `Mastery unlocks after ${4 - sessionState.turn_count} more turn(s).`
                  : ''}
              </p>
            )}

            <div className="max-w-2xl mx-auto">
              <InputArea onSend={onSend} disabled={loading || masteryLoading} />
            </div>

            <p className="text-center text-xs text-gray-300 mt-2">
              UB OT Tutor · Always verify important clinical information.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
