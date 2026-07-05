"""临床指南 / 健康知识 RAG Skill。"""

from __future__ import annotations

import asyncio
from typing import Optional

from rag.retriever import retrieve
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult


class GuidelineRagSkill(BaseSkill):
    skill_id = "guideline_rag"
    description = "检索与用户问题相关的健康知识、历史报告摘要与指南信息。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        query = ctx.message.strip() or "健康管理 general guidance"
        rag_result = await asyncio.to_thread(
            retrieve,
            ctx.user_id,
            {
                "scenario": "health_guideline",
                "query": query,
                "risk_focus": ctx.extra.get("risk_focus", ""),
            },
        )
        summary = rag_result.get("summary") or "（未检索到相关指南片段）"
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=rag_result,
            summary=str(summary)[:800],
            trace=[{"rag_debug": rag_result.get("debug")}],
        )
