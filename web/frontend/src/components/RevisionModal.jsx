import { useState } from 'react'
import { generateQuiz, resolveMistakes } from '../api'

const isInsufficient = (s) => !s || s.toLowerCase().includes('insufficient context')

const correctAnswerText = (answer) =>
  isInsufficient(answer)
    ? 'This concept wasn\'t fully covered in the reference material — review your course notes or textbook for this topic.'
    : answer

export default function RevisionModal({ weakSpot, onClose, onResolved }) {
  const [phase, setPhase]       = useState('intro')   // intro | loading | quiz | done
  const [questions, setQuestions] = useState([])
  const [current, setCurrent]   = useState(0)
  const [selected, setSelected] = useState(null)
  const [results, setResults]   = useState([])         // {correct: bool} per question
  const [error, setError]       = useState(null)

  const mistakeIds = weakSpot.mistakes.map((m) => m.id)

  const startQuiz = async () => {
    setPhase('loading')
    setError(null)
    try {
      const res = await generateQuiz(mistakeIds)
      setQuestions(res.data.questions)
      setCurrent(0)
      setSelected(null)
      setResults([])
      setPhase('quiz')
    } catch {
      setError('Failed to generate quiz. Please try again.')
      setPhase('intro')
    }
  }

  const handleSelect = (idx) => {
    if (selected !== null) return
    setSelected(idx)
  }

  const handleNext = () => {
    const q = questions[current]
    setResults((r) => [...r, { correct: selected === q.correct_index }])
    if (current + 1 < questions.length) {
      setCurrent((c) => c + 1)
      setSelected(null)
    } else {
      setPhase('done')
    }
  }

  const handleResolve = async () => {
    try {
      await resolveMistakes(mistakeIds)
      onResolved(weakSpot.topic)
    } catch {
      onClose()
    }
  }

  const q = questions[current]
  const correctCount = results.filter((r) => r.correct).length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Revision</p>
            <h2 className="text-base font-bold text-gray-900 mt-0.5 capitalize">{weakSpot.topic}</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">

          {/* ── Intro ── */}
          {phase === 'intro' && (
            <div>
              <p className="text-sm text-gray-600 mb-4">
                You made <span className="font-semibold text-red-600">{weakSpot.count} mistake{weakSpot.count !== 1 ? 's' : ''}</span> on this topic. Here's what went wrong:
              </p>
              <ul className="space-y-2 mb-5">
                {weakSpot.mistakes.map((m) => (
                  <li key={m.id} className="bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                    <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1">You said</p>
                    <p className="text-sm text-gray-800 italic">"{m.excerpt}"</p>
                    <>
                      <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mt-2 mb-1">Correct answer</p>
                      <p className={`text-sm ${isInsufficient(m.correct_answer) ? 'text-gray-400 italic' : 'text-gray-700'}`}>
                        {correctAnswerText(m.correct_answer)}
                      </p>
                    </>
                  </li>
                ))}
              </ul>
              {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
              <button
                onClick={startQuiz}
                className="w-full py-2.5 bg-ub-blue hover:bg-ub-blue-dk text-white text-sm font-semibold rounded-xl transition-colors"
              >
                Start Revision Quiz →
              </button>
            </div>
          )}

          {/* ── Loading ── */}
          {phase === 'loading' && (
            <div className="flex flex-col items-center py-10 gap-3">
              <div className="w-8 h-8 border-2 border-ub-blue border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-gray-400">Generating quiz questions…</p>
            </div>
          )}

          {/* ── Quiz ── */}
          {phase === 'quiz' && q && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs text-gray-400">Question {current + 1} of {questions.length}</span>
                <div className="flex gap-1">
                  {questions.map((_, i) => (
                    <div key={i} className={`w-2 h-2 rounded-full ${i < current ? 'bg-ub-blue' : i === current ? 'bg-ub-gold' : 'bg-gray-200'}`} />
                  ))}
                </div>
              </div>

              <p className="text-sm font-semibold text-gray-900 mb-4 leading-relaxed">{q.question}</p>

              <div className="space-y-2 mb-5">
                {q.options.map((opt, i) => {
                  let style = 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 cursor-pointer'
                  if (selected !== null) {
                    if (i === q.correct_index) style = 'border-emerald-400 bg-emerald-50 cursor-default'
                    else if (i === selected)   style = 'border-red-400 bg-red-50 cursor-default'
                    else                       style = 'border-gray-100 opacity-50 cursor-default'
                  }
                  return (
                    <button
                      key={i}
                      onClick={() => handleSelect(i)}
                      className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-colors ${style}`}
                    >
                      <span className="font-semibold text-gray-500 mr-2">{['A','B','C','D'][i]}.</span>
                      {opt}
                    </button>
                  )
                })}
              </div>

              {selected !== null && (
                <div className="mb-4">
                  <div className={`rounded-xl px-4 py-3 text-sm ${selected === q.correct_index ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}`}>
                    <span className="font-semibold">{selected === q.correct_index ? '✓ Correct! ' : '✗ Not quite. '}</span>
                    {q.explanation}
                  </div>
                </div>
              )}

              <button
                onClick={handleNext}
                disabled={selected === null}
                className="w-full py-2.5 bg-ub-blue hover:bg-ub-blue-dk disabled:bg-gray-200 text-white text-sm font-semibold rounded-xl transition-colors"
              >
                {current + 1 < questions.length ? 'Next Question →' : 'See Results →'}
              </button>
            </div>
          )}

          {/* ── Done ── */}
          {phase === 'done' && (
            <div className="text-center py-2">
              <div className={`w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center text-2xl ${
                correctCount === questions.length ? 'bg-emerald-50' : 'bg-amber-50'
              }`}>
                {correctCount === questions.length ? '🎉' : '📚'}
              </div>
              <p className="text-xl font-black text-gray-900">
                {correctCount} / {questions.length}
              </p>
              <p className="text-sm text-gray-500 mt-1 mb-6">
                {correctCount === questions.length
                  ? 'Perfect score — you\'ve got this!'
                  : correctCount >= questions.length / 2
                  ? 'Good effort — review the explanations above.'
                  : 'Keep reviewing — try again soon.'}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={startQuiz}
                  className="flex-1 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-xl transition-colors"
                >
                  Retry Quiz
                </button>
                <button
                  onClick={handleResolve}
                  className="flex-1 py-2.5 bg-ub-blue hover:bg-ub-blue-dk text-white text-sm font-semibold rounded-xl transition-colors"
                >
                  Mark Resolved ✓
                </button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
