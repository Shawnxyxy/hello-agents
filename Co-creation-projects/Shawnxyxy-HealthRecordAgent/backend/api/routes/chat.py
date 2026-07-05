"""健康助手对话 API。"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from chat.orchestrator import HealthAssistantOrchestrator
from memory.store import (
    create_chat_session,
    get_chat_session,
    list_chat_messages,
    list_chat_sessions_for_user,
    list_recent_chat_messages_for_user,
)

router = APIRouter()

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10MB

logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=256)

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id 不能为空")
        return v


@router.post("/chat/sessions")
async def create_session(body: CreateSessionRequest):
    session_id = str(uuid4())
    row = create_chat_session(body.user_id, session_id)
    return row


@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str, user_id: str):
    row = get_chat_session(session_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    if row["user_id"] != user_id.strip():
        raise HTTPException(status_code=403, detail="user_id 不匹配")
    return row


@router.get("/chat/sessions/{session_id}/history")
async def session_history(session_id: str, user_id: str, limit: int = 100):
    row = get_chat_session(session_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    if row["user_id"] != user_id.strip():
        raise HTTPException(status_code=403, detail="user_id 不匹配")
    messages = list_chat_messages(session_id.strip(), limit=limit)
    return {"session_id": session_id, "user_id": row["user_id"], "messages": messages}


@router.get("/chat/users/{user_id}/sessions")
async def user_chat_sessions(user_id: str, limit: int = 30):
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 无效")
    items = list_chat_sessions_for_user(uid, limit=limit)
    return {"user_id": uid, "items": items}


@router.get("/chat/users/{user_id}/recent_messages")
async def user_recent_chat_messages(user_id: str, limit: int = 40):
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 无效")
    items = list_recent_chat_messages_for_user(uid, limit=limit)
    return {"user_id": uid, "items": items}


async def _read_attachment(file: UploadFile | None) -> tuple[str | None, str | None, bytes | None]:
    """返回 (report_text 预览, filename, raw_bytes)。"""
    if not file or not file.filename:
        return None, None, None
    name = file.filename
    contents = await file.read()
    if len(contents) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="附件过大，请上传 10MB 以内的文件")
    if not contents:
        return None, name, None

    if contents[:4] == b"%PDF":
        return None, name, contents

    lower = name.lower()
    if lower.endswith(".txt"):
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return contents.decode(enc), name, contents
            except UnicodeDecodeError:
                continue
        return contents.decode("utf-8", errors="replace"), name, contents

    if lower.endswith(".pdf"):
        return None, name, contents

    raise HTTPException(status_code=400, detail="仅支持 .pdf 或 .txt 附件")


async def _extract_attachment_text(file: UploadFile | None) -> tuple[str | None, str | None]:
    """兼容旧测试：通过 ReportParsingPipeline 提取文本预览。"""
    text, name, raw = await _read_attachment(file)
    if not raw or not name:
        return text, name
    if text:
        return text, name
    from service.report_parsing import ReportParsingPipeline
    from service.report_parsing.errors import ParseError

    try:
        parsed = await ReportParsingPipeline().ingest_bytes_async(raw, name, skip_llm=True)
        return parsed.artifact.raw_text, name
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    user_id: str = Form(...),
    message: str = Form(""),
    file: UploadFile | None = File(None),
):
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    row = get_chat_session(session_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    if row["user_id"] != uid:
        raise HTTPException(status_code=403, detail="user_id 不匹配")

    report_text, attachment_name, attachment_bytes = await _read_attachment(file)
    if not message.strip() and not report_text and not attachment_bytes:
        raise HTTPException(status_code=400, detail="请输入消息或上传体检报告")

    orchestrator = HealthAssistantOrchestrator()

    async def event_stream():
        async for chunk in orchestrator.stream_response(
            session_id.strip(),
            uid,
            message,
            report_text=report_text,
            attachment_name=attachment_name,
            attachment_bytes=attachment_bytes,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
