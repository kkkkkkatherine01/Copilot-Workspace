"""generation.py 的纯逻辑单元测试：引用解析、历史拼接、低置信度短路。

这些测试不调用真实的 Claude API（用 mock 替换 Anthropic 客户端），
不产生费用，也不需要网络。
"""
from unittest.mock import MagicMock, patch

from generation import (
    GENERATION_ERROR_FALLBACK,
    LOW_CONFIDENCE_FALLBACK,
    _build_faq_context,
    _build_history_section,
    _parse_citation,
    generate_suggestion,
    rewrite_query_with_history,
)


def test_parse_citation_extracts_ids_and_strips_marker():
    raw = "这是回复内容。\n[参考: faq_001, faq_003]"
    text, ids = _parse_citation(raw, valid_ids={"faq_001", "faq_003", "faq_005"})
    assert text == "这是回复内容。"
    assert ids == ["faq_001", "faq_003"]


def test_parse_citation_filters_ids_not_in_valid_set():
    # LLM 偶尔会引用一个不在检索结果里的id，这种要过滤掉，不能原样信任模型输出
    raw = "回复。\n[参考: faq_001, faq_999]"
    _, ids = _parse_citation(raw, valid_ids={"faq_001"})
    assert ids == ["faq_001"]


def test_parse_citation_missing_marker_returns_no_citations():
    # LLM 没按格式输出引用标记时：不知道具体引用了哪条，宁可不声称引用，
    # 也不能把全部检索结果都标成"已引用"制造虚假的知识溯源信息（这是修复过的一个真实bug）
    raw = "没有按格式输出引用标记的回复"
    text, ids = _parse_citation(raw, valid_ids={"faq_001", "faq_002"})
    assert text == raw
    assert ids == []


def test_build_history_section_empty_when_no_history():
    assert _build_history_section(None) == ""
    assert _build_history_section([]) == ""


def test_build_history_section_formats_roles():
    history = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "回复"},
    ]
    section = _build_history_section(history)
    assert "用户：第一句" in section
    assert "客服：回复" in section


def test_build_faq_context_includes_id_question_answer():
    faqs = [{"id": "faq_001", "question": "Q1", "answer": "A1"}]
    context = _build_faq_context(faqs)
    assert "[faq_001]" in context
    assert "Q1" in context
    assert "A1" in context


def test_generate_suggestion_short_circuits_when_no_retrieved_faqs():
    with patch("generation.Anthropic") as mock_anthropic:
        result = generate_suggestion("随便问点什么", [])
        assert result["suggestion"] == LOW_CONFIDENCE_FALLBACK
        assert result["low_confidence"] is True
        assert result["referenced_faq_ids"] == []
        mock_anthropic.assert_not_called()


def test_generate_suggestion_short_circuits_below_threshold():
    with patch("generation.Anthropic") as mock_anthropic:
        retrieved = [{"id": "faq_001", "question": "Q", "answer": "A", "score": 0.2}]
        result = generate_suggestion("消息", retrieved, confidence_threshold=0.5)
        assert result["low_confidence"] is True
        mock_anthropic.assert_not_called()


def test_generate_suggestion_calls_api_when_confidence_sufficient():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="回复内容\n[参考: faq_001]")]

    with patch("generation.Anthropic") as mock_anthropic_cls:
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = fake_response

        retrieved = [{"id": "faq_001", "question": "Q", "answer": "A", "score": 0.9}]
        result = generate_suggestion("消息", retrieved, confidence_threshold=0.5)

        assert result["low_confidence"] is False
        assert result["suggestion"] == "回复内容"
        assert result["referenced_faq_ids"] == ["faq_001"]
        mock_client.messages.create.assert_called_once()


def test_rewrite_query_with_history_returns_stripped_text():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="  改写后的独立问题  ")]

    with patch("generation.Anthropic") as mock_anthropic_cls:
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value = fake_response

        history = [{"role": "user", "content": "第一轮问题"}]
        result = rewrite_query_with_history("这个还能用吗", history)

        assert result == "改写后的独立问题"
        mock_client.messages.create.assert_called_once()


def test_rewrite_query_with_history_falls_back_to_original_when_empty():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="   ")]

    with patch("generation.Anthropic") as mock_anthropic_cls:
        mock_anthropic_cls.return_value.messages.create.return_value = fake_response
        result = rewrite_query_with_history("原始问题", [{"role": "user", "content": "历史"}])
        assert result == "原始问题"


def test_rewrite_query_with_history_falls_back_to_original_on_api_error():
    # 查询改写不是核心链路，API调用失败（网络/限流等）不该让整个请求崩掉，
    # 应该退回原始消息去检索
    with patch("generation.Anthropic") as mock_anthropic_cls:
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception("network error")
        result = rewrite_query_with_history("原始问题", [{"role": "user", "content": "历史"}])
        assert result == "原始问题"


def test_generate_suggestion_returns_error_fallback_on_api_failure():
    with patch("generation.Anthropic") as mock_anthropic_cls:
        mock_anthropic_cls.return_value.messages.create.side_effect = Exception("rate limited")

        retrieved = [{"id": "faq_001", "question": "Q", "answer": "A", "score": 0.9}]
        result = generate_suggestion("消息", retrieved, confidence_threshold=0.5)

        assert result["suggestion"] == GENERATION_ERROR_FALLBACK
        assert result["low_confidence"] is True
        assert result["referenced_faq_ids"] == []
