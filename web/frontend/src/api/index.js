import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'
const api = axios.create({
  baseURL: BASE,
  headers: { 'ngrok-skip-browser-warning': 'true' },
})

export const createSession  = ()                       => api.post('/sessions')
export const listSessions   = ()                       => api.get('/sessions')
export const getSession     = (id)                     => api.get(`/sessions/${id}`)
export const deleteSession  = (id)                     => api.delete(`/sessions/${id}`)
export const getDashboard   = ()                       => api.get('/dashboard')

export const sendMessage = (sessionId, message, imageFile) => {
  const form = new FormData()
  form.append('message', message || '')
  if (imageFile) form.append('image', imageFile)
  return api.post(`/sessions/${sessionId}/chat`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const requestMastery  = (sessionId)  => api.post(`/sessions/${sessionId}/mastery`)

export const generateQuiz    = (mistakeIds) => api.post('/mistakes/quiz',    { mistake_ids: mistakeIds })
export const resolveMistakes = (mistakeIds) => api.post('/mistakes/resolve', { mistake_ids: mistakeIds })
