"""从会话关联的历史报告 run 构建追问上下文。"""

from __future__ import annotations

from typing import Optional

from memory.store import get_report_run
from skills.base import SkillResult
from skills.report_analysis_skill import build_report_summary, extract_report_inner


def build_prior_report_context(task_id: str, user_id: str) -> Optional[SkillResult]:
    """无新附件时，用 last_report_task_id 加载已分析报告摘要。"""
    row = get_report_run(task_id.strip())
    if not row or row.get("user_id") != user_id:
        return None

    inner = extract_report_inner({"report": row.get("report")})
    if not inner and row.get("summary_text"):
        inner = {"summary": row["summary_text"]}

    if not inner:
        return None

    return SkillResult(
        skill_id="prior_report_context",
        success=True,
        data={
            "task_id": task_id,
            "report_inner": inner,
            "created_at": row.get("created_at"),
        },
        summary=build_report_summary(inner),
        trace=[{"source": "last_report_task_id", "task_id": task_id}],
    )
