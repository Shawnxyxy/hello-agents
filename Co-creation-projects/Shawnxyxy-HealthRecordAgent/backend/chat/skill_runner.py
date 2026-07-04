"""Skill 安全执行封装。"""

from __future__ import annotations

import logging
from typing import Optional

from skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger(__name__)


async def run_skill_safe(
    skill: BaseSkill,
    ctx: SkillContext,
    *,
    on_progress=None,
) -> tuple[SkillResult, Optional[str]]:
    try:
        if on_progress is not None:
            result = await skill.run(ctx, on_progress=on_progress)
        else:
            result = await skill.run(ctx)
        return result, None
    except Exception as exc:
        logger.exception("Skill %s 执行失败", skill.skill_id)
        return (
            SkillResult(
                skill_id=skill.skill_id,
                success=False,
                summary=f"{skill.description[:20]}… 执行失败，请稍后重试。",
                trace=[{"error": str(exc)}],
                degraded=True,
            ),
            str(exc),
        )
