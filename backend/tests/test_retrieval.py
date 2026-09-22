"""retrieval.py 的纯逻辑单元测试：编码文本的拼接策略、上下文依赖判断的启发式。
不加载真正的 embedding 模型（那部分由 eval.py 做端到端准确率验证，不适合放进单元测试里跑）。
"""
from retrieval import _faq_to_text, looks_context_dependent


def test_faq_to_text_weights_keywords_twice_before_question():
    faq = {"question": "怎么退款？", "keywords": ["退款", "退货"]}
    text = _faq_to_text(faq)
    assert text == "退款 退货 退款 退货 怎么退款？"


def test_faq_to_text_handles_missing_keywords():
    faq = {"question": "怎么退款？"}
    text = _faq_to_text(faq)
    assert text.endswith("怎么退款？")


def test_looks_context_dependent_false_without_history():
    # 没有历史的话，压根谈不上"依赖上下文"，不管消息长什么样都不该触发改写
    assert looks_context_dependent("这个多少钱", has_history=False) is False


def test_looks_context_dependent_true_for_short_message_with_history():
    assert looks_context_dependent("能用吗", has_history=True) is True


def test_looks_context_dependent_true_for_pronoun_marker():
    assert looks_context_dependent("那如果我再买一件东西凑够金额，这张券还能用吗", has_history=True) is True


def test_looks_context_dependent_false_for_self_contained_long_message():
    # 特意包含"应该"：早期版本的标记词列表里有"该"，会被"应该"这种常见词误判，这里防止回归
    assert looks_context_dependent("我想问一下发票抬头写错了应该怎么修改", has_history=True) is False
