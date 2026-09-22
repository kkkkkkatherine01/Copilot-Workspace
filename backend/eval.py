"""用 test_conversations.json 验证检索准确率：分别报告 Top-1 和 Top-3 命中率。

只看 Top-1 会低估系统真实效果：生成阶段用的是 Top-3 而不是只用 Top-1，
即使 Top-1 排错了，只要正确答案在 Top-3 里，LLM 通常还是能从候选里挑出对的
（详见 BAD_CASE_ANALYSIS.md Case 1 的真实案例）。所以这里把两个指标分开报告，
不merge成一个笼统的"准确率"，避免掩盖"检索层面还有优化空间，但最终系统表现更好"这个事实。
"""
import os

from retrieval import FaqIndex, load_faqs

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def main():
    faqs = load_faqs(os.path.join(DATA_DIR, "faq.json"))
    conversations = load_faqs(os.path.join(DATA_DIR, "test_conversations.json"))
    index = FaqIndex(faqs)

    top1_hits = 0
    top3_hits = 0
    for conv in conversations:
        user_message = conv["messages"][0]["content"]
        expected = conv["expected_faq_id"]
        top_hits = index.retrieve(user_message, top_k=3)
        top1 = top_hits[0]
        retrieved_ids = [h["id"] for h in top_hits]

        is_top1_hit = top1["id"] == expected
        is_top3_hit = expected in retrieved_ids
        top1_hits += int(is_top1_hit)
        top3_hits += int(is_top3_hit)

        top1_status = "HIT" if is_top1_hit else "MISS"
        top3_status = "HIT" if is_top3_hit else "MISS"
        print(
            f"{conv['conversation_id']:10} [{conv['difficulty']:6}] "
            f"expected={expected:8} top1={top1['id']:8} score={top1['score']:.3f}  "
            f"top1={top1_status}  top3={top3_status}"
        )
        if not is_top1_hit:
            print(f"    用户消息: {user_message}")
            print(f"    实际 top-3: {[(h['id'], round(h['score'], 3)) for h in top_hits]}")

    total = len(conversations)
    print(f"\nTop-1 Accuracy: {top1_hits}/{total} ({top1_hits / total * 100:.0f}%)")
    print(f"Top-3 Recall:   {top3_hits}/{total} ({top3_hits / total * 100:.0f}%)")


if __name__ == "__main__":
    main()
