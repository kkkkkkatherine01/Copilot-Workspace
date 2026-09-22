"""FastAPI 应用：路由 + CORS + 启动时构建一次 FaqIndex 单例。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import db
from generation import DEFAULT_CONFIDENCE_THRESHOLD, generate_suggestion, rewrite_query_with_history
from models import FeedbackRequest, FeedbackResponse, SuggestRequest, SuggestResponse
from retrieval import FaqIndex, load_faqs, looks_context_dependent

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 应用状态：FaqIndex 和测试会话数据只在启动时加载一次，不在每次请求里重新构建
_state: dict = {}

# 每个 conversation_id 生成过多少条建议，用来拼 message_id（f"{conversation_id}_{序号}"）。
# 单进程内存计数，重启会归零，对 demo 场景可以接受（不影响功能，只影响 message_id 的连续性）。
_message_counters: dict[str, int] = {}


def _compute_display_confidence(retrieved_faqs: list[dict], referenced_faq_ids: list[str]) -> float:
    """展示给客服的匹配度，对应实际被引用的FAQ分数，而不是永远显示检索top-1的分数。
    否则会出现"匹配度显示60%，但被引用的是另一条55%的FAQ"这种看起来矛盾的情况
    （检索排序和生成阶段最终选谁是两个独立判断，见 BAD_CASE_ANALYSIS.md Case 1）。
    如果引用了多条，取分数最高的一条；如果没有任何FAQ被引用（低置信度短路、
    API异常、或LLM没标注引用），没有"被引用的FAQ"可参考，退回显示检索top-1的分数。
    """
    if not retrieved_faqs:
        return 0.0
    cited_scores = [f["score"] for f in retrieved_faqs if f["id"] in referenced_faq_ids]
    if cited_scores:
        return max(cited_scores)
    return retrieved_faqs[0]["score"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    faqs = load_faqs(os.path.join(DATA_DIR, "faq.json"))
    _state["faq_index"] = FaqIndex(faqs)
    _state["conversations"] = load_faqs(os.path.join(DATA_DIR, "test_conversations.json"))
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

# 本地开发 + 部署后的 Vercel 域名（通过 FRONTEND_ORIGIN 环境变量配置，不硬编码）
ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
if extra_origin := os.environ.get("FRONTEND_ORIGIN"):
    ALLOWED_ORIGINS.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/conversations")
def list_conversations():
    return [
        {
            "conversation_id": conv["conversation_id"],
            "first_message": conv["messages"][0]["content"],
            "difficulty": conv["difficulty"],
        }
        for conv in _state["conversations"]
    ]


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    for conv in _state["conversations"]:
        if conv["conversation_id"] == conversation_id:
            return conv
    raise HTTPException(status_code=404, detail="conversation not found")


@app.post("/api/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest):
    faq_index: FaqIndex = _state["faq_index"]

    # 检索本身不感知历史，但对"这张券还能用吗"这类依赖上下文的追问，
    # 先用历史把它改写成一句独立的问题再检索，效果比直接拿原句检索好得多（见 BAD_CASE_ANALYSIS.md）。
    # 只在看起来像有指代/省略的时候才触发，避免给每条消息都多付一次LLM调用成本。
    retrieval_query = req.user_message
    if looks_context_dependent(req.user_message, has_history=bool(req.history)):
        retrieval_query = rewrite_query_with_history(req.user_message, req.history)

    retrieved = faq_index.retrieve(retrieval_query, top_k=3)
    result = generate_suggestion(req.user_message, retrieved, history=req.history)

    _message_counters[req.conversation_id] = _message_counters.get(req.conversation_id, 0) + 1
    message_id = f"{req.conversation_id}_{_message_counters[req.conversation_id]}"

    confidence = _compute_display_confidence(retrieved, result["referenced_faq_ids"])
    # 只要生成阶段本身判定为低置信度（检索太弱没调用LLM、或API调用失败），
    # 就一定展示警示，不管这里重新计算出的分数是多少
    low_confidence = result["low_confidence"] or confidence < DEFAULT_CONFIDENCE_THRESHOLD

    return SuggestResponse(
        message_id=message_id,
        suggestion=result["suggestion"],
        retrieved_faqs=retrieved,
        referenced_faq_ids=result["referenced_faq_ids"],
        confidence=confidence,
        low_confidence=low_confidence,
    )


@app.post("/api/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest):
    db.insert_feedback(req)
    return FeedbackResponse(success=True)
