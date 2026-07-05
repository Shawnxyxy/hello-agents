"""历史报告趋势对比 Skill。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Dict, Optional

from models.health_trend import TrendAnalysis, TrendDirection
from service.trend_analysis import TrendAnalysisService
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult

TREND_KEYWORDS = (
    "对比",
    "上次",
    "趋势",
    "变化",
    "改善",
    "恶化",
    "进步",
    "历史",
    "比一下",
    "有没有好转",
)


def _trend_to_dict(trend: TrendAnalysis) -> Dict[str, Any]:
    data = asdict(trend)
    data["overall_trend"] = trend.overall_trend.value
    for comp in data.get("comparison_data") or []:
        if isinstance(comp, dict) and "change_type" in comp:
            ct = comp["change_type"]
            if hasattr(ct, "value"):
                comp["change_type"] = ct.value
    return data


def _build_summary(trend: TrendAnalysis, comparisons_count: int) -> str:
    parts = [trend.summary]
    if comparisons_count:
        parts.append(f"本次对比 {comparisons_count} 项指标")
    if trend.recommendations:
        parts.append("建议：" + "；".join(trend.recommendations[:2]))
    return " ".join(p for p in parts if p)


class TrendCompareSkill(BaseSkill):
    skill_id = "trend_compare"
    description = "对比用户历史体检报告，分析指标趋势与变化。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        force = bool(ctx.extra.get("force_trend"))
        if not force and not any(k in ctx.message for k in TREND_KEYWORDS):
            if not ctx.last_report_task_id:
                return SkillResult(
                    skill_id=self.skill_id,
                    success=False,
                    summary="当前消息未识别为趋势/对比类请求。",
                    trace=[{"skipped": True}],
                )

        if on_progress:
            on_progress(
                "skill_progress",
                {"skill": self.skill_id, "stage": "analyze", "label": "趋势分析", "status": "running"},
            )

        svc = TrendAnalysisService()
        trend = await asyncio.to_thread(svc.analyze_trends, ctx.user_id, 90)
        comparisons = await asyncio.to_thread(svc.compare_with_previous, ctx.user_id)

        if on_progress:
            on_progress(
                "skill_progress",
                {"skill": self.skill_id, "stage": "analyze", "label": "趋势分析", "status": "completed"},
            )

        trend_dict = _trend_to_dict(trend)
        comp_count = len(comparisons)
        success = trend.overall_trend != TrendDirection.UNKNOWN or comp_count > 0

        return SkillResult(
            skill_id=self.skill_id,
            success=success,
            data={"trend": trend_dict, "comparisons_count": comp_count},
            summary=_build_summary(trend, comp_count),
            trace=[{"comparisons": comp_count, "overall": trend.overall_trend.value}],
            degraded=not success,
        )
