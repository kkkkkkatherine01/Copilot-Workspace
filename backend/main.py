"""FastAPI 应用：路由 + CORS + 启动时构建一次 FaqIndex 单例。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import db
from generation import generate_suggestion, rewrite_query_with_history
from models import FeedbackRequest, FeedbackResponse, SuggestRequest, SuggestResponse
from retrieval import FaqIndex, load_faqs, looks_context_dependent

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 应用状态：FaqIndex 和测试会话数据只在启动时加载一次，不在每次请求里重新构建
_state: dict = {}

# 每个 conversation_id 生成过多少条建议，用来拼 message_id（f"{conversation_id}_{序号}"）。
# 单进程内存计数，重启会归零，对 demo 场景可以接受（不影响功能，只影响 message_id 的连续性）。
_message_counters: dict[str, int] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    faqs = load_faqs(os.path.join(DATA_DIR, "faq.json"))
    _state["faq_index"] = FaqIndex(faqs)
    _state["conversations"] = load_faqs(os.path.join(DATA_DIR, "test_conversations.json"))
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

# 本地开发 + 部署后的 Vercel 域名（阶段11部署时回填真实域名）
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

    confidence = retrieved[0]["score"] if retrieved else 0.0

    return SuggestResponse(
        message_id=message_id,
        suggestion=result["suggestion"],
        retrieved_faqs=retrieved,
        referenced_faq_ids=result["referenced_faq_ids"],
        confidence=confidence,
        low_confidence=result["low_confidence"],
    )


@app.post("/api/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest):
    db.insert_feedback(req)
    return FeedbackResponse(success=True)
