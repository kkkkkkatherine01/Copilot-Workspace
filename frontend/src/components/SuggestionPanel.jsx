// 这个分数是检索时的 cosine similarity，不是校准过的"预测正确概率"，
// 命名和展示上统一用"匹配度"而不是"置信度"，避免暗示一个我们没有做过的统计校准。
// 详见 README「知识溯源与FAQ匹配度」一节的说明。
function matchScoreLabel(score) {
  if (score >= 0.7) return { text: '高', className: 'confidence-high' }
  if (score >= 0.5) return { text: '中', className: 'confidence-medium' }
  return { text: '低', className: 'confidence-low' }
}

function SuggestionPanel({ loading, suggestion, editedText, onEditedTextChange, onAccept, onEdit, onIgnore, actionTaken, submitting }) {
  const matchScore = suggestion ? matchScoreLabel(suggestion.confidence) : null
  const isEdited = suggestion && editedText !== suggestion.suggestion

  return (
    <div className="panel suggestion-panel">
      <div className="panel-header">
        <h2>Copilot 建议</h2>
        {matchScore && !loading && (
          <span className={`confidence-badge ${matchScore.className}`}>
            FAQ匹配度：{matchScore.text}（{(suggestion.confidence * 100).toFixed(0)}%）
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
              <div className="low-confidence-banner">⚠️ FAQ匹配度较低，请谨慎核实后再发送</div>
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
