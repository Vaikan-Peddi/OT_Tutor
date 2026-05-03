import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDashboard } from '../api'
import RevisionModal from '../components/RevisionModal'

function StatCard({ label, value, sub, highlight = false }) {
  return (
    <div className={`rounded-2xl border p-5 ${highlight ? 'bg-ub-blue border-ub-blue text-white' : 'bg-white border-gray-200'}`}>
      <p className={`text-xs font-bold uppercase tracking-wider mb-1.5 ${highlight ? 'text-blue-200' : 'text-gray-400'}`}>
        {label}
      </p>
      <p className={`text-3xl font-black tabular-nums ${highlight ? 'text-white' : 'text-gray-900'}`}>
        {value ?? '—'}
      </p>
      {sub && (
        <p className={`text-xs mt-1 ${highlight ? 'text-blue-200' : 'text-gray-400'}`}>{sub}</p>
      )}
    </div>
  )
}

function QualityBar({ label, count, total }) {
  const pct = total ? Math.round((count / total) * 100) : 0
  const barColors = {
    correct:    'bg-emerald-500',
    partial:    'bg-ub-gold',
    wrong:      'bg-red-500',
    unanswered: 'bg-gray-200',
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-28 capitalize">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${barColors[label] ?? 'bg-gray-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm text-gray-500 w-8 text-right tabular-nums">{count}</span>
      <span className="text-xs text-gray-400 w-9 text-right tabular-nums">{pct}%</span>
    </div>
  )
}

export default function DashboardPage() {
  const [data,          setData]          = useState(null)
  const [loading,       setLoading]       = useState(true)
  const [revising,      setRevising]      = useState(null)   // weakSpot object | null
  const [tooltipId,     setTooltipId]     = useState(null)   // mistake id with open tooltip
  const navigate = useNavigate()

  const loadDashboard = () => {
    getDashboard()
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadDashboard() }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-white">
        <p className="text-gray-400 text-sm">Loading dashboard…</p>
      </div>
    )
  }

  if (!data) return null

  const totalAttempts = Object.values(data.quality_breakdown).reduce((a, b) => a + b, 0)

  const handleResolved = (topic) => {
    setRevising(null)
    // Remove the resolved topic from weak_spots optimistically
    setData((d) => ({ ...d, weak_spots: d.weak_spots.filter((ws) => ws.topic !== topic) }))
  }

  return (
    <>
    <div className="h-full overflow-y-auto bg-gray-50 scrollbar-thin">
      <div className="max-w-4xl mx-auto px-8 py-8 space-y-8">

        {/* Header */}
        <div className="flex items-center gap-4 pb-6 border-b border-gray-200">
          <img src="/ub-logo.png" alt="University at Buffalo" className="h-10" />
          <div>
            <h1 className="text-2xl font-black text-gray-900 leading-tight">Student Dashboard</h1>
            <p className="text-gray-500 text-sm mt-0.5">OT Tutor · Performance Overview</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Sessions"        value={data.total_sessions}   highlight />
          <StatCard label="Avg Assessment Score"  value={data.avg_score != null ? `${data.avg_score}/100` : null} sub="assessment phase only" />
          <StatCard label="Mastery Complete"      value={data.mastery_completed} />
          <StatCard label="Total Attempts"        value={totalAttempts} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Weak Spots */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-4 rounded-full bg-red-400" />
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Weak Spots</h2>
            </div>
            {data.weak_spots.length === 0 ? (
              <p className="text-gray-400 text-sm">No weak spots yet — keep it up!</p>
            ) : (
              <ul className="space-y-2">
                {data.weak_spots.map((ws) => (
                  <li key={ws.topic} className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
                    {/* Topic row */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-gray-800 capitalize">{ws.topic}</span>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs bg-red-50 text-red-600 border border-red-100 px-2 py-0.5 rounded-full font-semibold">
                          {ws.count} mistake{ws.count !== 1 ? 's' : ''}
                        </span>
                        <button
                          onClick={() => setRevising(ws)}
                          className="text-xs px-2.5 py-1 bg-ub-blue hover:bg-ub-blue-dk text-white font-semibold rounded-lg transition-colors"
                        >
                          Revise →
                        </button>
                      </div>
                    </div>
                    {/* Mistake excerpts */}
                    <ul className="mt-2 space-y-1">
                      {ws.mistakes.map((m) => (
                        <li key={m.id} className="relative">
                          <button
                            className="w-full text-left"
                            onClick={() => setTooltipId(tooltipId === m.id ? null : m.id)}
                          >
                            <p className="text-xs text-gray-500 italic truncate hover:text-gray-700 transition-colors">
                              "{m.excerpt}"
                            </p>
                          </button>
                          {tooltipId === m.id && (
                            <div className="mt-1.5 bg-white border border-emerald-200 rounded-xl px-3 py-2.5 shadow-sm">
                              <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-wide mb-1">Correct Answer</p>
                              {m.correct_answer && !m.correct_answer.toLowerCase().includes('insufficient context') ? (
                                <p className="text-xs text-gray-700 leading-relaxed">{m.correct_answer}</p>
                              ) : (
                                <p className="text-xs text-gray-400 italic leading-relaxed">
                                  Not enough reference material was found for this topic — review your course notes.
                                </p>
                              )}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Answer Quality */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-4 rounded-full bg-ub-blue" />
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Answer Quality</h2>
            </div>
            {totalAttempts === 0 ? (
              <p className="text-gray-400 text-sm">No attempts recorded yet.</p>
            ) : (
              <div className="space-y-3.5">
                {Object.entries(data.quality_breakdown).map(([q, c]) => (
                  <QualityBar key={q} label={q} count={c} total={totalAttempts} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent Sessions */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-ub-blue" />
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">Recent Sessions</h2>
          </div>
          {data.recent_sessions.length === 0 ? (
            <p className="text-gray-400 text-sm">No sessions yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="pb-3 font-semibold pr-4">Topic / Question</th>
                  <th className="pb-3 font-semibold pr-4">Phase</th>
                  <th className="pb-3 font-semibold pr-4">Turns</th>
                  <th className="pb-3 font-semibold pr-4">Score</th>
                  <th className="pb-3 font-semibold">Mastery</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.recent_sessions.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/chat/${s.id}`)}
                    className="cursor-pointer hover:bg-ub-blue/5 transition-colors group"
                  >
                    <td className="py-3 pr-4 font-medium text-gray-800 group-hover:text-ub-blue transition-colors truncate max-w-[200px]">
                      {s.topic_label || s.question?.slice(0, 50) || s.id}
                    </td>
                    <td className="py-3 pr-4 text-gray-500 capitalize">{s.phase}</td>
                    <td className="py-3 pr-4 text-gray-500 tabular-nums">{s.turn_count}</td>
                    <td className="py-3 pr-4 tabular-nums">
                      {s.avg_score != null ? (
                        <span className="text-ub-blue font-semibold">{s.avg_score}/100</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-3">
                      {s.mastery_done
                        ? <span className="text-ub-gold font-bold">✓</span>
                        : <span className="text-gray-300">—</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>

    {revising && (
      <RevisionModal
        weakSpot={revising}
        onClose={() => setRevising(null)}
        onResolved={handleResolved}
      />
    )}
    </>
  )
}
