import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import SessionSidebar from '../components/SessionSidebar'
import ChatWindow from '../components/ChatWindow'
import { listSessions, getSession, sendMessage, requestMastery } from '../api'

export default function ChatPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [sessions, setSessions] = useState([])
  const [messages, setMessages] = useState([])
  const [sessionState, setSessionState] = useState(null)
  const [loading, setLoading] = useState(false)
  const [masteryLoading, setMasteryLoading] = useState(false)

  const refreshSessions = useCallback(async () => {
    try {
      const res = await listSessions()
      setSessions(res.data)
    } catch (_) {}
  }, [])

  // Load session list on mount
  useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  // Load session detail whenever the active session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      setSessionState(null)
      return
    }
    refreshSessions()
    getSession(sessionId)
      .then((res) => {
        const s = res.data
        setMessages(s.messages || [])
        setSessionState({
          phase: s.phase,
          turn_count: s.turn_count,
          mastery_unlocked: s.mastery_unlocked,
          mastery_done: s.mastery_done,
          topic_label: s.topic_label,
          question: s.question,
          image_mode: s.image_mode,
          image_identified_as: s.image_identified_as,
        })
      })
      .catch(() => navigate('/chat'))
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async (message, imageFile) => {
    if (!sessionId) return

    // Optimistic user message
    setMessages((prev) => [
      ...prev,
      {
        id: `tmp-${Date.now()}`,
        role: 'user',
        content: imageFile ? message || '[image uploaded]' : message,
        timestamp: new Date().toISOString(),
        is_mastery: false,
      },
    ])
    setLoading(true)

    try {
      const res = await sendMessage(sessionId, message, imageFile)
      const { reply, phase, turn_count, mastery_unlocked, mastery_done, topic_label } = res.data

      setMessages((prev) => [
        ...prev,
        {
          id: `tmp-${Date.now()}`,
          role: 'assistant',
          content: reply,
          timestamp: new Date().toISOString(),
          is_mastery: false,
        },
      ])

      setSessionState((prev) => ({
        ...prev,
        phase,
        turn_count,
        mastery_unlocked,
        mastery_done,
        topic_label: topic_label || prev?.topic_label,
      }))

      refreshSessions()
    } catch (err) {
      const detail = err.response?.data?.detail || 'Something went wrong. Please try again.'
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'error',
          content: detail,
          timestamp: new Date().toISOString(),
          is_mastery: false,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleMastery = async () => {
    if (!sessionId) return
    setMasteryLoading(true)
    try {
      const res = await requestMastery(sessionId)
      setMessages((prev) => [
        ...prev,
        {
          id: `mastery-${Date.now()}`,
          role: 'assistant',
          content: res.data.mastery_text,
          timestamp: new Date().toISOString(),
          is_mastery: true,
        },
      ])
      setSessionState((prev) => ({ ...prev, mastery_done: true }))
      refreshSessions()
    } catch (err) {
      console.error('Mastery error', err)
    } finally {
      setMasteryLoading(false)
    }
  }

  return (
    <div className="flex h-full">
      <SessionSidebar sessions={sessions} activeSessionId={sessionId} />
      <ChatWindow
        sessionId={sessionId}
        sessionState={sessionState}
        messages={messages}
        loading={loading}
        masteryLoading={masteryLoading}
        onSend={handleSend}
        onMastery={handleMastery}
      />
    </div>
  )
}
