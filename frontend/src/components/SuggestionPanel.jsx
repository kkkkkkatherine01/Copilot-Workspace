function confidenceLabel(score) {
  if (score >= 0.7) return { text: '高', className: 'confidence-high' }
  if (score >= 0.5) return { text: '中', className: 'confidence-medium' }
  return { text: '低', className: 'confidence-low' }
}

function SuggestionPanel({ loading, suggestion, editedText, onEditedTextChange, onAccept, onEdit, onIgnore, actionTaken, submitting }) {
  const confidence = suggestion ? confidenceLabel(suggestion.confidence) : null
  const isEdited = suggestion && editedText !== suggestion.suggestion

  return (
    <div className="panel suggestion-panel">
      <div className="panel-header">
        <h2>Copilot 建议</h2>
        {confidence && !loading && (
          <span className={`confidence-badge ${confidence.className}`}>
            置信度：{confidence.text}（{(suggestion.confidence * 100).toFixed(0)}%）
          </span>
        )}
      </div>

      <div className="panel-body">
        {loading && <div className="loading-hint">生成中...</div>}
        {!loading && !suggestion && (
          <div className="empty-hint">在左侧发一条消息，这里会实时生成回复建议</div>
        )}
        {!loading && suggestion && (
          <>
            {suggestion.low_confidence && (
              <div className="low-confidence-banner">⚠️ 低置信度，请谨慎核实后再发送</div>
            )}

            <textarea
              className="suggestion-textarea"
              value={editedText}
              onChange={(e) => onEditedTextChange(e.target.value)}
              disabled={!!actionTaken}
              rows={6}
            />

            {suggestion.retrieved_faqs.length > 0 && (
              <div className="faq-sources">
                <h3>知识溯源</h3>
                {suggestion.retrieved_faqs.map((faq) => {
                  const cited = suggestion.referenced_faq_ids?.includes(faq.id)
                  return (
                    <div key={faq.id} className={`faq-card ${cited ? 'faq-card-cited' : ''}`}>
                      <div className="faq-card-header">
                        <span className="faq-id">[{faq.id}]</span>
                        <span className="faq-question">{faq.question}</span>
                        {cited && <span className="cited-tag">已引用</span>}
                        <span className="faq-score">{(faq.score * 100).toFixed(0)}%</span>
                      </div>
                      <div className="faq-card-answer">{faq.answer}</div>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>

      {!loading && suggestion && (
        <div className="panel-footer">
          <div className="action-buttons">
            <button disabled={!!actionTaken || submitting} onClick={onAccept}>
              采纳
            </button>
            <button disabled={!!actionTaken || submitting || !isEdited} onClick={onEdit}>
              编辑后发送
            </button>
            <button disabled={!!actionTaken || submitting} onClick={onIgnore} className="ignore-btn">
              忽略
            </button>
          </div>
          {actionTaken && <div className="action-status">已处理：{actionTaken}</div>}
        </div>
      )}
    </div>
  )
}

export default SuggestionPanel
