"""用 test_conversations.json 验证检索准确率：检索到的 top-1 FAQ 是否命中 expected_faq_id。"""
import os

from retrieval import FaqIndex, load_faqs

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def main():
    faqs = load_faqs(os.path.join(DATA_DIR, "faq.json"))
    conversations = load_faqs(os.path.join(DATA_DIR, "test_conversations.json"))
    index = FaqIndex(faqs)

    hits = 0
    for conv in conversations:
        user_message = conv["messages"][0]["content"]
        expected = conv["expected_faq_id"]
        top_hits = index.retrieve(user_message, top_k=3)
        top1 = top_hits[0]
        is_hit = top1["id"] == expected
        hits += int(is_hit)
        status = "HIT" if is_hit else "MISS"
        print(
            f"{conv['conversation_id']:10} [{conv['difficulty']:6}] "
            f"expected={expected:8} top1={top1['id']:8} score={top1['score']:.3f}  {status}"
        )
        if not is_hit:
            print(f"    用户消息: {user_message}")
            print(f"    实际 top-3: {[(h['id'], round(h['score'], 3)) for h in top_hits]}")

    total = len(conversations)
    print(f"\nAccuracy: {hits}/{total} ({hits / total * 100:.0f}%)")


if __name__ == "__main__":
    main()
