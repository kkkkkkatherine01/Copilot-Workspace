"""FastAPI 请求/响应用的 Pydantic 数据模型。"""
from typing import Literal

from pydantic import BaseModel


class FaqHit(BaseModel):
    id: str
    category: str
    question: str
    answer: str
    score: float


class SuggestRequest(BaseModel):
    conversation_id: str
    user_message: str
    history: list[dict] = []  # 之前的对话轮次 [{role, content}, ...]，用于多轮上下文感知


class SuggestResponse(BaseModel):
    message_id: str
    suggestion: str
    retrieved_faqs: list[FaqHit]
    referenced_faq_ids: list[str]
    confidence: float
    low_confidence: bool


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    user_message: str
    retrieved_faq_ids: list[str]
    confidence_score: float
    suggestion: str
    final_reply: str
    action: Literal["采纳", "编辑", "忽略"]


class FeedbackResponse(BaseModel):
    success: bool
