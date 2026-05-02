import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDashboard } from '../api'

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
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getDashboard()
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-white">
        <p className="text-gray-400 text-sm">Loading dashboard…</p>
      </div>
    )
  }

  if (!data) return null

  const totalAttempts = Object.values(data.quality_breakdown).reduce((a, b) => a + b, 0)

  return (
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
              <ul className="divide-y divide-gray-50">
                {data.weak_spots.map((ws) => (
                  <li key={ws.topic} className="flex items-center justify-between py-2.5">
                    <span className="text-sm text-gray-700 font-medium">{ws.topic}</span>
                    <span className="text-xs bg-red-50 text-red-600 border border-red-100 px-2 py-0.5 rounded-full font-semibold">
                      {ws.count} mistake{ws.count !== 1 ? 's' : ''}
                    </span>
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
  )
}
