"""向量检索模块：加载 FAQ、编码为向量、按 cosine similarity 取 top-k。"""
import json
import os

import numpy as np
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "shibing624/text2vec-base-chinese"


def load_faqs(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _faq_to_text(faq: dict) -> str:
    # 只编码 question + keywords，不编码 answer：
    # 用户消息在语义上更接近"问题"而不是"答案"。
    # keywords 重复拼接两次做加权：keywords 是人工标注的意图信号，
    # 实测（eval.py）发现加权后能明显提升区分度（尤其是同一分类下多条相似FAQ的场景），
    # 比如"付了三次都失败了，钱也没扣"这类case，不加权时会被"重复支付"类FAQ抢走top1。
    keywords_text = " ".join(faq.get("keywords", []))
    return keywords_text + " " + keywords_text + " " + faq["question"]


class FaqIndex:
    """FAQ 向量索引，进程内只应初始化一次（FastAPI 里作为单例持有）。"""

    def __init__(self, faqs: list[dict], model_name: str = DEFAULT_MODEL_NAME):
        self.faqs = faqs
        self.model = SentenceTransformer(model_name)
        texts = [_faq_to_text(f) for f in faqs]
        # normalize_embeddings=True 之后，向量已经是单位向量，
        # cosine similarity 直接用点积计算即可，不用再除以模长
        self.embeddings = self.model.encode(texts, normalize_embeddings=True)

    def retrieve(self, user_message: str, top_k: int = 3) -> list[dict]:
        query_vec = self.model.encode([user_message], normalize_embeddings=True)[0]
        scores = self.embeddings @ query_vec
        top_indices = np.argsort(-scores)[:top_k]
        return [
            {
                "id": self.faqs[i]["id"],
                "category": self.faqs[i]["category"],
                "question": self.faqs[i]["question"],
                "answer": self.faqs[i]["answer"],
                "score": float(scores[i]),
            }
            for i in top_indices
        ]


if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    faqs = load_faqs(os.path.join(data_dir, "faq.json"))
    index = FaqIndex(faqs)

    test_messages = [
        "我买的东西到了，但是屏幕碎了，怎么处理？",
        "今天天气怎么样",  # 故意问一个和客服无关的问题，检查低分表现
    ]
    for msg in test_messages:
        print(f"\n用户消息: {msg}")
        for hit in index.retrieve(msg):
            print(f"  {hit['id']} (score={hit['score']:.3f}) {hit['question']}")
