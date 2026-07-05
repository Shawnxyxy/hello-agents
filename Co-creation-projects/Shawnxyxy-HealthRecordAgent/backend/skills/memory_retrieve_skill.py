"""记忆检索 Skill。"""

from __future__ import annotations

import asyncio
from typing import Optional

from rag.retriever import retrieve
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult


class MemoryRetrieveSkill(BaseSkill):
    skill_id = "memory_retrieve"
    description = "检索用户历史体检、饮食与反馈记忆，供对话上下文使用。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        query = ctx.message.strip() or "用户健康历史与执行反馈"
        rag_result = await asyncio.to_thread(
            retrieve,
            ctx.user_id,
            {"scenario": "health_chat", "query": query},
        )
        summary = rag_result.get("summary") or "（暂无相关历史记忆）"
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=rag_result,
            summary=str(summary)[:800],
            trace=[{"rag_debug": rag_result.get("debug")}],
        )
