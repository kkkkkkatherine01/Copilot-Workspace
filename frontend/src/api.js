const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

async function request(path, options) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status} ${await res.text()}`)
  }
  return res.json()
}

export function listConversations() {
  return request('/api/conversations')
}

export function getConversation(conversationId) {
  return request(`/api/conversations/${conversationId}`)
}

export function requestSuggestion(conversationId, userMessage, history = []) {
  return request('/api/suggest', {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, user_message: userMessage, history }),
  })
}

export function submitFeedback(payload) {
  return request('/api/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
