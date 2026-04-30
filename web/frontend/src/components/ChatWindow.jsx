import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'

const PHASE_META = {
  tutoring:   { label: 'Socratic Hints',      color: 'bg-amber-100 text-amber-800' },
  reveal:     { label: 'Answer Revealed',     color: 'bg-blue-100 text-blue-800' },
  assessment: { label: 'Clinical Assessment', color: 'bg-purple-100 text-purple-800' },
  mastery:    { label: 'Mastery Complete',    color: 'bg-emerald-100 text-emerald-800' },
}

function PhaseIndicator({ phase }) {
  const { label, color } = PHASE_META[phase] || { label: phase, color: 'bg-gray-100 text-gray-700' }
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${color}`}>{label}</span>
  )
}

function TypingDots() {
  return (
    <div className="flex justify-start">
      <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-4">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
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

  if (!sessionId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-xs px-4">
          <p className="text-4xl mb-4">🦴</p>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Welcome to OT Tutor</h2>
          <p className="text-gray-500 text-sm leading-relaxed">
            Press <strong>+ New Session</strong> above to start a Socratic tutoring session, or pick
            a previous one from the sidebar.
          </p>
        </div>
      </div>
    )
  }

  const masteryAvailable = sessionState?.mastery_unlocked && !sessionState?.mastery_done

  return (
    <div className="flex-1 flex flex-col h-full bg-white overflow-hidden">
      {/* Header */}
      <div className="px-6 py-3 border-b border-gray-200 flex items-center gap-3 shrink-0">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate">
            {sessionState?.topic_label || sessionState?.question || `Session ${sessionId}`}
          </p>
          {sessionState?.image_identified_as && (
            <p className="text-xs text-gray-400 truncate">
              Image: {sessionState.image_identified_as}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {sessionState?.phase && <PhaseIndicator phase={sessionState.phase} />}
          <span className="text-xs text-gray-400 tabular-nums">
            Turn {sessionState?.turn_count ?? 0}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4 scrollbar-thin">
        {messages.map((msg, i) => (
          <MessageBubble key={msg.id ?? i} message={msg} />
        ))}
        {loading && <TypingDots />}
        <div ref={bottomRef} />
      </div>

      {/* Footer: Mastery button + Input */}
      <div className="border-t border-gray-200 px-6 pt-3 pb-4 shrink-0 space-y-2">
        {/* Mastery row */}
        <div className="flex justify-between items-center">
          <p className="text-xs text-gray-400">
            {masteryAvailable
              ? 'You have unlocked the mastery summary.'
              : sessionState?.mastery_done
              ? ''
              : sessionState?.turn_count != null
              ? `Mastery unlocks after turn ${4 - (sessionState.turn_count || 0) > 0 ? `${4 - sessionState.turn_count} more turn(s)` : 'now'}.`
              : ''}
          </p>
          {(masteryAvailable || sessionState?.mastery_done) && (
            <button
              onClick={masteryAvailable ? onMastery : undefined}
              disabled={masteryLoading || sessionState?.mastery_done}
              className={`px-4 py-1.5 text-sm font-semibold rounded-lg transition-colors ${
                sessionState?.mastery_done
                  ? 'bg-emerald-100 text-emerald-700 cursor-default'
                  : masteryLoading
                  ? 'bg-emerald-100 text-emerald-600 cursor-wait'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              {sessionState?.mastery_done
                ? '✓ Mastery Complete'
                : masteryLoading
                ? 'Generating…'
                : 'Mastery Summary'}
            </button>
          )}
        </div>

        <InputArea onSend={onSend} disabled={loading || masteryLoading} />
      </div>
    </div>
  )
}
