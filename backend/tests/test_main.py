"""main.py 里"展示的匹配度对齐实际引用的FAQ"这条逻辑的单元测试。"""
from main import _compute_display_confidence


def test_confidence_uses_cited_faq_score_not_top1():
    # 这就是真实遇到的case：top1是faq_013(0.60)，但Claude引用的是faq_003(0.55)，
    # 展示的匹配度应该跟着"已引用"走，显示0.55，而不是没被引用的0.60
    retrieved = [
        {"id": "faq_013", "score": 0.60},
        {"id": "faq_014", "score": 0.59},
        {"id": "faq_003", "score": 0.55},
    ]
    confidence = _compute_display_confidence(retrieved, referenced_faq_ids=["faq_003"])
    assert confidence == 0.55


def test_confidence_takes_max_when_multiple_cited():
    retrieved = [
        {"id": "faq_004", "score": 0.80},
        {"id": "faq_017", "score": 0.65},
    ]
    confidence = _compute_display_confidence(retrieved, referenced_faq_ids=["faq_004", "faq_017"])
    assert confidence == 0.80


def test_confidence_falls_back_to_top1_when_nothing_cited():
    # 低置信度短路 / API异常 / LLM没标注引用，都会导致referenced_faq_ids为空，
    # 这时候没有"被引用的FAQ"可以参考，退回显示检索最高分
    retrieved = [{"id": "faq_001", "score": 0.42}, {"id": "faq_002", "score": 0.30}]
    confidence = _compute_display_confidence(retrieved, referenced_faq_ids=[])
    assert confidence == 0.42


def test_confidence_zero_when_nothing_retrieved():
    assert _compute_display_confidence([], referenced_faq_ids=[]) == 0.0
