import { useState, useRef, useEffect } from 'react'

export default function InputArea({ onSend, disabled }) {
  const [text,         setText]         = useState('')
  const [imageFile,    setImageFile]    = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [isRecording,  setIsRecording]  = useState(false)
  const fileRef     = useRef(null)
  const textareaRef = useRef(null)
  const recognitionRef = useRef(null)

  const isSpeechRecognitionSupported = typeof window !== 'undefined' && (
    'SpeechRecognition' in window || 'webkitSpeechRecognition' in window
  )

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 144) + 'px'
  }, [text])

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop()
    }
  }, [])

  const startListening = () => {
    if (!isSpeechRecognitionSupported || disabled) return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const transcript = event.results[0][0]?.transcript || ''
      if (!transcript) return
      setText((prev) => prev ? `${prev} ${transcript}` : transcript)
    }

    recognition.onerror = () => {
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsRecording(false)
      recognitionRef.current = null
    }

    recognition.start()
    recognitionRef.current = recognition
    setIsRecording(true)
  }

  const stopListening = () => {
    recognitionRef.current?.stop()
    recognitionRef.current = null
    setIsRecording(false)
  }

  const handleMicClick = () => {
    if (!isSpeechRecognitionSupported || disabled) return
    if (isRecording) {
      stopListening()
      return
    }
    startListening()
  }

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

        {/* Speech input */}
        <button
          onClick={handleMicClick}
          disabled={!isSpeechRecognitionSupported || disabled}
          title={isSpeechRecognitionSupported ? (isRecording ? 'Stop voice input' : 'Start voice input') : 'Speech-to-text is not supported in this browser'}
          className="shrink-0 p-1.5 text-gray-400 hover:text-ub-blue hover:bg-ub-blue/8 rounded-lg transition-colors disabled:opacity-40 mb-0.5"
          aria-pressed={isRecording}
        >
          <svg className={`w-5 h-5 ${isRecording ? 'text-ub-blue' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 1.75a3.75 3.75 0 00-3.75 3.75v4.5a3.75 3.75 0 007.5 0v-4.5A3.75 3.75 0 0012 1.75z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M19.5 10.75a7.5 7.5 0 01-15 0" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 18.25v3" />
          </svg>
        </button>

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
