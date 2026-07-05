"""prior_report_context 与 chat 附件解析测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from chat.report_context import build_prior_report_context
from memory.store import (
    append_chat_message,
    create_chat_session,
    ensure_user,
    init_db,
    save_completed_report_run,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("HEALTH_MEMORY_DB_PATH", str(db_path))
    init_db()
    yield


def test_build_prior_report_context_from_saved_run():
    ensure_user("u1")
    final = {
        "report": {
            "summary": " LDL 偏高",
            "risk_section": {"overall_risk_level": "medium"},
            "indicator_section": [{"name": "LDL"}],
            "advice_section": ["少油"],
        }
    }
    save_completed_report_run("u1", "task-abc", final, {})
    ctx = build_prior_report_context("task-abc", "u1")
    assert ctx is not None
    assert ctx.success is True
    assert "LDL" in ctx.summary or "medium" in ctx.summary
    assert build_prior_report_context("task-abc", "other-user") is None


def test_build_prior_report_context_missing():
    assert build_prior_report_context("no-such-task", "u1") is None


def test_list_recent_chat_messages_for_user():
    from memory.store import list_recent_chat_messages_for_user

    sid = "sess-1"
    create_chat_session("u2", sid)
    append_chat_message(sid, "user", "你好")
    append_chat_message(sid, "assistant", "你好，有什么可以帮你？")
    items = list_recent_chat_messages_for_user("u2", limit=10)
    assert len(items) == 2
    roles = {i["role"] for i in items}
    assert roles == {"user", "assistant"}


import asyncio


def test_extract_attachment_rejects_oversized():
    from api.routes.chat import MAX_ATTACHMENT_BYTES, _extract_attachment_text

    big = MagicMock()
    big.filename = "big.pdf"
    big.read = AsyncMock(return_value=b"x" * (MAX_ATTACHMENT_BYTES + 1))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_extract_attachment_text(big))
    assert exc.value.status_code == 413


def test_extract_attachment_pdf_error():
    from api.routes.chat import _extract_attachment_text

    f = MagicMock()
    f.filename = "bad.pdf"
    f.read = AsyncMock(return_value=b"not-a-pdf")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_extract_attachment_text(f))
    assert exc.value.status_code == 400
