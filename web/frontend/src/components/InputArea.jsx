import { useState, useRef, useEffect } from 'react'

export default function InputArea({ onSend, disabled }) {
  const [text,         setText]         = useState('')
  const [imageFile,    setImageFile]    = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const fileRef     = useRef(null)
  const textareaRef = useRef(null)

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 144) + 'px'
  }, [text])

  const handleSubmit = () => {
    const msg = text.trim()
    if (!msg && !imageFile) return
    onSend(msg, imageFile, imagePreview)
    setText('')
    setImageFile(null)
    setImagePreview(null)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFile = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = (ev) => setImagePreview(ev.target.result)
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const canSend = !disabled && (text.trim() || imageFile)

  return (
    <div className={`relative bg-white rounded-2xl border transition-all shadow-sm ${
      disabled ? 'border-gray-200 opacity-70' : 'border-gray-300 hover:border-gray-400 focus-within:border-ub-blue focus-within:ring-2 focus-within:ring-ub-blue/20'
    }`}>
      {/* Image preview strip */}
      {imagePreview && (
        <div className="px-4 pt-3 pb-1">
          <div className="relative inline-block">
            <img
              src={imagePreview}
              alt="upload preview"
              className="h-16 rounded-xl border border-gray-200 object-cover"
            />
            <button
              onClick={() => { setImageFile(null); setImagePreview(null) }}
              className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-gray-700 hover:bg-gray-900 text-white rounded-full text-xs flex items-center justify-center leading-none transition-colors"
            >×</button>
          </div>
        </div>
      )}

      <div className="flex items-end gap-2 px-3 py-2.5">
        {/* Image upload */}
        <button
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
          title="Upload anatomy image"
          className="shrink-0 p-1.5 text-gray-400 hover:text-ub-blue hover:bg-ub-blue/8 rounded-lg transition-colors disabled:opacity-40 mb-0.5"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={imageFile ? 'Add a question about this image… (optional)' : 'Ask a question or type your answer…'}
          className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none overflow-hidden leading-relaxed py-1"
          style={{ minHeight: '36px' }}
        />

        {/* Send button — circle */}
        <button
          onClick={handleSubmit}
          disabled={!canSend}
          className="shrink-0 w-8 h-8 bg-ub-blue hover:bg-ub-blue-dk disabled:bg-gray-200 text-white rounded-full flex items-center justify-center transition-colors mb-0.5 shadow-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
              d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  )
}
