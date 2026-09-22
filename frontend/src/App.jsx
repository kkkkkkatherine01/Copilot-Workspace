import { useEffect, useState } from 'react'
import ConversationPanel from './components/ConversationPanel'
import SuggestionPanel from './components/SuggestionPanel'
import { listConversations, getConversation, requestSuggestion, submitFeedback } from './api'
import './App.css'

function newSessionId() {
  return `session_${Date.now()}`
}

function App() {
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [messages, setMessages] = useState([])
  const [currentUserMessage, setCurrentUserMessage] = useState(null)
  const [suggestion, setSuggestion] = useState(null)
  const [editedText, setEditedText] = useState('')
  const [actionTaken, setActionTaken] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    listConversations().then(setConversations).catch((e) => setError(e.message))
  }, [])

  // 对一条用户消息（无论来自加载的测试场景，还是自由输入的新消息）
  // 统一走这条路径：重置上一轮的建议状态，调用 /api/suggest，更新建议面板
  async function generateForMessage(conversationId, userMessage, history = []) {
    setSuggestion(null)
    setEditedText('')
    setActionTaken(null)
    setError(null)
    setCurrentUserMessage(userMessage)
    try {
      setLoading(true)
      const result = await requestSuggestion(conversationId, userMessage, history)
      setSuggestion(result)
      setEditedText(result.suggestion)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // 加载一个测试场景仅作为"对话起点"（可选），不是发起对话的前提条件
  async function handleLoadScenario(conversationId) {
    if (!conversationId) return
    setSelectedId(conversationId)
    setError(null)
    try {
      const conv = await getConversation(conversationId)
      const nonEmptyMessages = conv.messages.filter((m) => m.content.trim() !== '')
      setMessages(nonEmptyMessages)

      const lastUserMessage = [...nonEmptyMessages].reverse().find((m) => m.role === 'user')
      if (lastUserMessage) {
        const idx = nonEmptyMessages.lastIndexOf(lastUserMessage)
        const history = nonEmptyMessages.slice(0, idx)
        await generateForMessage(conversationId, lastUserMessage.content, history)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  function handleReset() {
    setSelectedId(null)
    setMessages([])
    setSuggestion(null)
    setEditedText('')
    setActionTaken(null)
    setError(null)
  }

  // 客户自由输入新消息：如果还没有会话（既没加载测试场景，也没发过消息），
  // 现场生成一个新的 session id，不强制要求先加载测试数据
  async function handleSendMessage(text) {
    let conversationId = selectedId
    if (!conversationId) {
      conversationId = newSessionId()
      setSelectedId(conversationId)
    }
    const history = messages
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    await generateForMessage(conversationId, text, history)
  }

  async function handleAction(action, finalReply, { appendToConversation }) {
    setSubmitting(true)
    setError(null)
    try {
      await submitFeedback({
        conversation_id: selectedId,
        message_id: suggestion.message_id,
        user_message: currentUserMessage,
        retrieved_faq_ids: suggestion.retrieved_faqs.map((f) => f.id),
        confidence_score: suggestion.confidence,
        suggestion: suggestion.suggestion,
        final_reply: finalReply,
        action,
      })
      if (appendToConversation) {
        setMessages((prev) => [...prev, { role: 'assistant', content: finalReply }])
      }
      setActionTaken(action)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>客服 Copilot 工作台</h1>
      </header>
      <div className="app-layout">
        {error && <div className="error-banner">{error}</div>}
        <ConversationPanel
          conversations={conversations}
          selectedId={selectedId}
          onSelectScenario={handleLoadScenario}
          onReset={handleReset}
          messages={messages}
          onSendMessage={handleSendMessage}
          sending={loading}
        />
        <SuggestionPanel
          loading={loading}
          suggestion={suggestion}
          editedText={editedText}
          onEditedTextChange={setEditedText}
          onAccept={() => handleAction('采纳', suggestion.suggestion, { appendToConversation: true })}
          onEdit={() => handleAction('编辑', editedText, { appendToConversation: true })}
          onIgnore={() => handleAction('忽略', suggestion.suggestion, { appendToConversation: false })}
          actionTaken={actionTaken}
          submitting={submitting}
        />
      </div>
    </div>
  )
}

export default App
