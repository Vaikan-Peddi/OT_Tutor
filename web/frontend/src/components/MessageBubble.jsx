import ReactMarkdown from 'react-markdown'

export default function MessageBubble({ message }) {
  const { role, content, is_mastery } = message

  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm">
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>
        </div>
      </div>
    )
  }

  if (role === 'error') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] bg-red-50 border border-red-200 text-red-700 rounded-2xl rounded-tl-sm px-4 py-2.5">
          <p className="text-sm">{content}</p>
        </div>
      </div>
    )
  }

  if (is_mastery) {
    return (
      <div className="w-full">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4 shadow-sm">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-emerald-200">
            <span className="text-emerald-700 font-semibold text-sm">Mastery Summary</span>
            <span className="bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide">
              Complete
            </span>
          </div>
          <div className="prose prose-sm prose-emerald max-w-none text-gray-800">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2.5 shadow-sm">
        <div className="prose prose-sm max-w-none text-gray-800 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
