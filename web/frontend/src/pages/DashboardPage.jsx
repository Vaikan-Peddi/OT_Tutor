import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDashboard } from '../api'

function StatCard({ label, value, color = 'blue' }) {
  const colors = {
    blue:   'bg-blue-50   text-blue-800   border-blue-100',
    green:  'bg-green-50  text-green-800  border-green-100',
    purple: 'bg-purple-50 text-purple-800 border-purple-100',
    amber:  'bg-amber-50  text-amber-800  border-amber-100',
  }
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <p className="text-xs font-semibold uppercase tracking-wider opacity-60 mb-1">{label}</p>
      <p className="text-3xl font-bold">{value ?? '—'}</p>
    </div>
  )
}

function QualityBar({ label, count, total }) {
  const pct = total ? Math.round((count / total) * 100) : 0
  const barColors = {
    correct:    'bg-green-500',
    partial:    'bg-amber-400',
    wrong:      'bg-red-500',
    unanswered: 'bg-gray-300',
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-28 capitalize">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${barColors[label] ?? 'bg-gray-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm text-gray-500 w-8 text-right tabular-nums">{count}</span>
      <span className="text-xs text-gray-400 w-8 tabular-nums">{pct}%</span>
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState(null)
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
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-400 text-sm">Loading dashboard…</p>
      </div>
    )
  }

  if (!data) return null

  const totalAttempts = Object.values(data.quality_breakdown).reduce((a, b) => a + b, 0)

  return (
    <div className="h-full overflow-y-auto bg-gray-50 px-8 py-8 scrollbar-thin">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* Title */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Student Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Performance overview — single student, all sessions
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total Sessions"    value={data.total_sessions}   color="blue"   />
          <StatCard label="Avg Score"         value={data.avg_score != null ? `${data.avg_score}/100` : null} color="green"  />
          <StatCard label="Mastery Done"      value={data.mastery_completed} color="purple" />
          <StatCard label="Total Attempts"    value={totalAttempts}          color="amber"  />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Weak Spots */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800 mb-4 uppercase tracking-wide">
              Weak Spots
            </h2>
            {data.weak_spots.length === 0 ? (
              <p className="text-gray-400 text-sm">
                No weak spots yet — keep up the good work!
              </p>
            ) : (
              <ul className="divide-y divide-gray-50">
                {data.weak_spots.map((ws) => (
                  <li key={ws.topic} className="flex items-center justify-between py-2.5">
                    <span className="text-sm text-gray-700 font-medium">{ws.topic}</span>
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold">
                      {ws.count} mistake{ws.count !== 1 ? 's' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Answer Quality */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-800 mb-4 uppercase tracking-wide">
              Answer Quality
            </h2>
            {totalAttempts === 0 ? (
              <p className="text-gray-400 text-sm">No attempts recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(data.quality_breakdown).map(([q, c]) => (
                  <QualityBar key={q} label={q} count={c} total={totalAttempts} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent Sessions table */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-800 mb-4 uppercase tracking-wide">
            Recent Sessions
          </h2>
          {data.recent_sessions.length === 0 ? (
            <p className="text-gray-400 text-sm">No sessions yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="pb-2 font-semibold pr-4">Topic / Question</th>
                  <th className="pb-2 font-semibold pr-4">Phase</th>
                  <th className="pb-2 font-semibold pr-4">Turns</th>
                  <th className="pb-2 font-semibold pr-4">Score</th>
                  <th className="pb-2 font-semibold">Mastery</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.recent_sessions.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => navigate(`/chat/${s.id}`)}
                    className="cursor-pointer hover:bg-gray-50 transition-colors"
                  >
                    <td className="py-2.5 pr-4 text-gray-800 font-medium truncate max-w-[220px]">
                      {s.topic_label || s.question?.slice(0, 50) || s.id}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-500 capitalize">{s.phase}</td>
                    <td className="py-2.5 pr-4 text-gray-500 tabular-nums">{s.turn_count}</td>
                    <td className="py-2.5 pr-4 text-gray-500 tabular-nums">
                      {s.avg_score != null ? `${s.avg_score}/100` : '—'}
                    </td>
                    <td className="py-2.5">
                      {s.mastery_done ? (
                        <span className="text-emerald-600 font-medium">✓</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
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
