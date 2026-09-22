"""retrieval.py 的纯逻辑单元测试：只测编码文本的拼接策略，
不加载真正的 embedding 模型（那部分由 eval.py 做端到端准确率验证，不适合放进单元测试里跑）。
"""
from retrieval import _faq_to_text


def test_faq_to_text_weights_keywords_twice_before_question():
    faq = {"question": "怎么退款？", "keywords": ["退款", "退货"]}
    text = _faq_to_text(faq)
    assert text == "退款 退货 退款 退货 怎么退款？"


def test_faq_to_text_handles_missing_keywords():
    faq = {"question": "怎么退款？"}
    text = _faq_to_text(faq)
    assert text.endswith("怎么退款？")
