"""生成模块：组装 prompt、调用 Claude API 生成客服回复建议。"""
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "claude-haiku-4-5-20251001"
DEFAULT_CONFIDENCE_THRESHOLD = 0.5
LOW_CONFIDENCE_FALLBACK = "未找到明确匹配的知识条目，建议人工核实后再回复用户。"

# [参考: faq_001, faq_003] 这种格式，用于从 LLM 输出里解析引用的 FAQ id
_CITATION_PATTERN = re.compile(r"\[参考[:：]\s*([^\]]+)\]")

PROMPT_TEMPLATE_V1 = """你是电商平台的客服助手，任务是根据下面提供的FAQ知识库内容，为人工客服生成一条可以直接发给用户的回复建议。

严格遵守以下规则：
1. 只能使用下面提供的FAQ内容作答，不能编造FAQ中没有出现的具体信息（比如天数、金额、流程细节）。
2. 语气专业、友好，像真实客服说话，不要暴露"我是根据FAQ回答"这类内部逻辑。
3. 回复正文结束后另起一行，用固定格式标注本次参考的FAQ id，格式必须是：[参考: faq_001, faq_003]（如果参考了多条就都列出来，用英文逗号分隔；只能引用下面确实提供了的FAQ id）。

以下是检索到的相关FAQ：
{faq_context}
{history_section}
用户消息：{user_message}

请生成客服回复建议："""

# V2 相对 V1 的改进方向（详见 PROMPT_ITERATION.md 的实测对比）：
# 1. 限制长度和格式：V1 经常输出 markdown 加粗、分点列表，读起来不像真实客服聊天窗口里的一句话回复
# 2. 要求把用户消息里的具体数字/场景代入结论：V1 有时只给通用规则（"达到门槛即可使用"），
#    不会明确说"再买XX元、凑够XX元"这种针对性表述
# 3. 去掉"亲"这种偏淘宝客服的口语化开场，符合更通用的电商客服语气
PROMPT_TEMPLATE_V2 = """你是电商平台的客服助手，为人工客服生成一条可以直接发给用户的回复建议。

严格遵守以下规则：
1. 只能使用下面提供的FAQ内容作答，不能编造FAQ中没有出现的具体信息（天数、金额、流程细节等）。
2. 回复风格要求：
   - 开头用简短的致歉/感谢开场（如"您好"、"感谢您的耐心等待"），不要用"亲"这类过于口语化的称呼
   - 正文控制在3句话以内，直接给结论和下一步操作，不要用分点列表、不要用markdown加粗或标题
   - 不要复述用户的问题
3. 如果用户消息里包含具体的数字或场景（金额、时间等），必须把这些数字代入结论明确回答，
   不能只给通用规则（比如用户问"180元的东西能不能用满200的券"，要直接说明"还差多少元、能不能用"，
   而不是只说"达到门槛即可使用"）。
4. 回复正文结束后另起一行，用固定格式标注参考的FAQ id：[参考: faq_001, faq_003]（只能引用下面提供了的FAQ id，多条用英文逗号分隔）。

以下是检索到的相关FAQ：
{faq_context}
{history_section}
用户消息：{user_message}

请生成客服回复建议："""

PROMPT_TEMPLATES = {"v1": PROMPT_TEMPLATE_V1, "v2": PROMPT_TEMPLATE_V2}
DEFAULT_PROMPT_VERSION = "v2"  # 实测效果更好（见 PROMPT_ITERATION.md），设为默认


def _build_faq_context(retrieved_faqs: list[dict]) -> str:
    lines = []
    for faq in retrieved_faqs:
        lines.append(f"- [{faq['id']}] 问：{faq['question']}\n  答：{faq['answer']}")
    return "\n".join(lines)


def _build_history_section(history: list[dict] | None) -> str:
    if not history:
        return ""
    role_label = {"user": "用户", "assistant": "客服"}
    lines = [f"{role_label.get(m['role'], m['role'])}：{m['content']}" for m in history]
    return (
        "\n以下是之前的对话历史，仅用于理解上下文，不要在回复中重复历史内容：\n"
        + "\n".join(lines)
        + "\n"
    )


def _parse_citation(raw_text: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    match = _CITATION_PATTERN.search(raw_text)
    if not match:
        # LLM 没按格式输出引用标记，兜底返回全部检索到的 FAQ id，
        # 同时不删除任何文本（没有标记可删）
        return raw_text.strip(), list(valid_ids)

    cited_ids = [x.strip() for x in match.group(1).split(",") if x.strip() in valid_ids]
    clean_text = raw_text[: match.start()].strip()
    return clean_text, cited_ids


def generate_suggestion(
    user_message: str,
    retrieved_faqs: list[dict],
    history: list[dict] | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict:
    top_score = retrieved_faqs[0]["score"] if retrieved_faqs else 0.0
    low_confidence = top_score < confidence_threshold

    if not retrieved_faqs or low_confidence:
        # 置信度太低时不调用 LLM：让 LLM 自由发挥反而增加编造风险，
        # 不如用确定性代码兜底，这也是"是否该生成"这个决策不交给LLM自己判断的体现
        return {
            "suggestion": LOW_CONFIDENCE_FALLBACK,
            "referenced_faq_ids": [],
            "low_confidence": True,
        }

    valid_ids = {faq["id"] for faq in retrieved_faqs}
    prompt = PROMPT_TEMPLATES[prompt_version].format(
        faq_context=_build_faq_context(retrieved_faqs),
        history_section=_build_history_section(history),
        user_message=user_message,
    )

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text
    suggestion, referenced_faq_ids = _parse_citation(raw_text, valid_ids)

    return {
        "suggestion": suggestion,
        "referenced_faq_ids": referenced_faq_ids,
        "low_confidence": False,
    }


if __name__ == "__main__":
    from retrieval import FaqIndex, load_faqs
    import json

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    faqs = load_faqs(os.path.join(data_dir, "faq.json"))
    conversations = load_faqs(os.path.join(data_dir, "test_conversations.json"))
    index = FaqIndex(faqs)

    test_cases = [c["messages"][0]["content"] for c in conversations]
    test_cases.append("今天天气怎么样")  # 低置信度兜底测试

    for msg in test_cases:
        retrieved = index.retrieve(msg, top_k=3)
        result = generate_suggestion(msg, retrieved)
        print(f"\n用户消息: {msg}")
        print(f"检索top1: {retrieved[0]['id'] if retrieved else None} (score={retrieved[0]['score']:.3f})" if retrieved else "检索: 无结果")
        print(f"low_confidence: {result['low_confidence']}")
        print(f"引用: {result['referenced_faq_ids']}")
        print(f"建议: {result['suggestion']}")

    # 多轮上下文感知测试：第二轮消息单独看语义会很模糊（"这张券"指代不明），
    # 只有带上第一轮的历史，检索+生成才能正确理解在问什么
    print("\n" + "=" * 40 + " 多轮上下文测试 " + "=" * 40)
    turn1 = "我有个满200减30的券，买了一个180的东西能用吗？"
    turn2 = "那如果我再买一件20块的凑够200，这张券还能用吗？"

    retrieved1 = index.retrieve(turn1, top_k=3)
    result1 = generate_suggestion(turn1, retrieved1)
    print(f"\n第1轮用户消息: {turn1}")
    print(f"第1轮建议: {result1['suggestion']}")

    history = [
        {"role": "user", "content": turn1},
        {"role": "assistant", "content": result1["suggestion"]},
    ]
    retrieved2_no_history = index.retrieve(turn2, top_k=3)
    result2_no_history = generate_suggestion(turn2, retrieved2_no_history)
    print(f"\n第2轮用户消息（不带历史）: {turn2}")
    print(f"检索top1: {retrieved2_no_history[0]['id']} (score={retrieved2_no_history[0]['score']:.3f})")
    print(f"建议（不带历史）: {result2_no_history['suggestion']}")

    result2_with_history = generate_suggestion(turn2, retrieved2_no_history, history=history)
    print(f"\n第2轮建议（带历史，检索结果相同，只是生成阶段能看到上下文）: {result2_with_history['suggestion']}")
