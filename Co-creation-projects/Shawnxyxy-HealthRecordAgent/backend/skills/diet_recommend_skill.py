"""饮食推荐 Skill — 包装现有 DietMultiAgentPipeline。"""

from __future__ import annotations

import re
from typing import Optional

from service.diet_recommend_service import DietRecommendService
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult

DIET_KEYWORDS = re.compile(
    r"吃|饮食|餐|热量|蛋白|减脂|增肌|早餐|午餐|晚餐|零食|营养|卡路里|食物"
)


class DietRecommendSkill(BaseSkill):
    skill_id = "diet_recommend"
    description = "根据用户饮食记录与健康目标，生成下一餐可执行建议。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        message = ctx.message.strip()
        if not DIET_KEYWORDS.search(message) and not ctx.extra.get("force_diet"):
            return SkillResult(
                skill_id=self.skill_id,
                success=False,
                summary="当前消息未识别为饮食相关请求。",
                trace=[{"skipped": True}],
            )

        if on_progress:
            on_progress("skill_progress", {"skill": self.skill_id, "stage": "pipeline", "label": "饮食分析", "status": "running"})

        context = {
            "goal": ctx.extra.get("goal") or "maintain",
            "today_food_log_text": message,
            "activity_sleep_text": ctx.extra.get("activity_sleep_text") or "",
        }
        svc = DietRecommendService()
        result = await svc.run(ctx.user_id, context)

        meal_plan = result.get("meal_plan") or result.get("output", {}).get("meal_plan") or {}
        summary = ""
        if isinstance(meal_plan, dict):
            summary = str(meal_plan.get("summary") or meal_plan.get("next_meal_suggestion") or "")[:400]
        if not summary:
            summary = "已生成饮食建议，请查看下一餐推荐。"

        if on_progress:
            on_progress("skill_progress", {"skill": self.skill_id, "stage": "pipeline", "label": "饮食分析", "status": "completed"})

        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=result,
            summary=summary,
            trace=result.get("steps_trace") or result.get("pipeline_trace") or [],
            degraded=bool(result.get("degraded")),
        )
