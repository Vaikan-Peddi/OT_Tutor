import { useState, useRef, useEffect } from 'react'

export default function InputArea({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const fileRef = useRef(null)
  const textareaRef = useRef(null)

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }, [text])

  const handleSubmit = () => {
    const msg = text.trim()
    if (!msg && !imageFile) return
    onSend(msg, imageFile)
    setText('')
    setImageFile(null)
    setImagePreview(null)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
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

  const removeImage = () => {
    setImageFile(null)
    setImagePreview(null)
  }

  const canSend = !disabled && (text.trim() || imageFile)

  return (
    <div className="space-y-2">
      {imagePreview && (
        <div className="relative inline-block">
          <img
            src={imagePreview}
            alt="upload"
            className="h-16 rounded-lg border border-gray-200 object-cover"
          />
          <button
            onClick={removeImage}
            className="absolute -top-1.5 -right-1.5 bg-gray-800 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center leading-none hover:bg-gray-700"
          >
            ×
          </button>
        </div>
      )}

      <div className="flex items-end gap-2">
        {/* Image upload */}
        <button
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
          title="Upload anatomy image"
          className="shrink-0 p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-40"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={
            imageFile
              ? 'Add a question about this image (optional)…'
              : 'Ask a question or type your answer… (Enter to send)'
          }
          className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 overflow-hidden"
          style={{ minHeight: '44px' }}
        />

        {/* Send */}
        <button
          onClick={handleSubmit}
          disabled={!canSend}
          className="shrink-0 p-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-200 text-white rounded-xl transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    </div>
  )
}
