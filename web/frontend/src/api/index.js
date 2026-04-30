import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

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

export const requestMastery = (sessionId) => api.post(`/sessions/${sessionId}/mastery`)
