"""安全审查 Skill — Harness 输出约束。"""

from __future__ import annotations

from typing import Optional

from harness.output_reviewer import review_assistant_output
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult


class SafetyGuardSkill(BaseSkill):
    skill_id = "safety_guard"
    description = "审查助手输出是否符合医疗安全边界，附加免责声明与高危提醒。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        draft = str(ctx.extra.get("draft_response") or "")
        user_input = ctx.message
        review = review_assistant_output(user_input, draft)
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data={
                "text": review.text,
                "high_risk_flags": review.high_risk_flags,
                "forbidden_issues": review.forbidden_issues,
                "modified": review.modified,
            },
            summary=review.text[:200],
            trace=[{"modified": review.modified, "flags": review.high_risk_flags}],
        )
