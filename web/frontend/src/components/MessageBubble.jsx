import ReactMarkdown from 'react-markdown'

function UBAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-ub-blue flex items-center justify-center shrink-0 shadow-sm">
      {/* Robot / agent icon */}
      <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4" xmlns="http://www.w3.org/2000/svg">
        {/* Antenna */}
        <line x1="10" y1="2" x2="10" y2="5" stroke="#FFB81C" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="10" cy="1.5" r="1" fill="#FFB81C"/>
        {/* Head */}
        <rect x="4" y="5" width="12" height="9" rx="2.5" fill="white" fillOpacity="0.92"/>
        {/* Eyes */}
        <circle cx="7.5" cy="9" r="1.4" fill="#005BBB"/>
        <circle cx="12.5" cy="9" r="1.4" fill="#005BBB"/>
        <circle cx="7.9" cy="8.6" r="0.45" fill="white"/>
        <circle cx="12.9" cy="8.6" r="0.45" fill="white"/>
        {/* Mouth */}
        <rect x="7" y="11.5" width="6" height="1" rx="0.5" fill="#005BBB" fillOpacity="0.5"/>
        {/* Ears / side bolts */}
        <rect x="2.5" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
        <rect x="16" y="7.5" width="1.5" height="3" rx="0.75" fill="white" fillOpacity="0.6"/>
        {/* Body */}
        <rect x="6" y="14.5" width="8" height="4" rx="1.5" fill="white" fillOpacity="0.7"/>
        <rect x="8.25" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
        <rect x="10.55" y="15.2" width="1.2" height="2.5" rx="0.6" fill="#FFB81C" fillOpacity="0.8"/>
      </svg>
    </div>
  )
}

export default function MessageBubble({ message }) {
  const { role, content, is_mastery } = message

  // ── User ───────────────────────────────────────────────────────────────
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[72%] space-y-2">
          {message.imagePreview && (
            <div className="flex justify-end">
              <img
                src={message.imagePreview}
                alt="uploaded"
                className="max-h-56 max-w-full rounded-2xl border border-gray-200 object-contain shadow-sm"
              />
            </div>
          )}
          {content && (
            <div className="bg-gray-100 text-gray-900 rounded-3xl rounded-br-md px-5 py-3">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (role === 'error') {
    return (
      <div className="flex gap-3">
        <div className="w-7 h-7 rounded-full bg-red-100 border border-red-200 flex items-center justify-center shrink-0">
          <span className="text-red-500 text-xs font-bold">!</span>
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          <p className="text-sm text-red-600 leading-relaxed">{content}</p>
        </div>
      </div>
    )
  }

  // ── Mastery ────────────────────────────────────────────────────────────
  if (is_mastery) {
    return (
      <div className="flex gap-3">
        <UBAvatar />
        <div className="flex-1 min-w-0">
          <div className="bg-ub-gold/10 border border-ub-gold/30 rounded-2xl px-5 py-4">
            <div className="flex items-center gap-2 mb-3 pb-2.5 border-b border-ub-gold/20">
              <span className="text-ub-blue font-bold text-sm">Mastery Summary</span>
              <span className="ml-auto bg-ub-gold text-ub-navy text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide">
                Complete
              </span>
            </div>
            <div className="prose prose-sm max-w-none text-gray-800">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── Assistant ──────────────────────────────────────────────────────────
  return (
    <div className="flex gap-3">
      <UBAvatar />
      <div className="flex-1 min-w-0 pt-0.5">
        <div className="prose prose-sm max-w-none text-gray-800 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
