import { useEffect, useRef, useState } from 'react'

function ConversationPanel({ conversations, selectedId, onSelectScenario, onReset, messages, onSendMessage, sending }) {
  const [draft, setDraft] = useState('')
  const listRef = useRef(null)

  // 每次消息列表变化都滚到底部，模拟真实聊天窗口的行为
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  function handleSend() {
    if (!draft.trim()) return
    onSendMessage(draft.trim())
    setDraft('')
  }

  return (
    <div className="panel conversation-panel">
      <div className="panel-header">
        <h2>用户对话</h2>
      </div>

      <div className="scenario-bar">
        <select value={selectedId ?? ''} onChange={(e) => onSelectScenario(e.target.value)}>
          <option value="">加载测试场景（可选，仅作为对话起点）</option>
          {conversations.map((c) => (
            <option key={c.conversation_id} value={c.conversation_id}>
              [{c.difficulty}] {c.conversation_id} — {c.first_message}
            </option>
          ))}
        </select>
        {(selectedId || messages.length > 0) && (
          <button type="button" className="reset-btn" onClick={onReset}>
            新对话
          </button>
        )}
      </div>

      <div className="message-list" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty-hint">在下方输入框里模拟用户发消息，即可开始对话</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <span className="message-role">{m.role === 'user' ? '用户' : '客服'}</span>
            <p>{m.content}</p>
          </div>
        ))}
      </div>

      <div className="composer">
        <input
          type="text"
          placeholder="模拟用户输入消息..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          disabled={sending}
        />
        <button onClick={handleSend} disabled={sending || !draft.trim()}>
          发送
        </button>
      </div>
    </div>
  )
}

export default ConversationPanel
