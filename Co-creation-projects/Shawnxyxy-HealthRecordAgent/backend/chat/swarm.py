"""Agent Swarm — 并行调度多个 Skill。"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from chat.skill_runner import run_skill_safe
from skills.base import BaseSkill, SkillContext, SkillResult

SwarmProgressCallback = Callable[[str, str, Dict[str, Any]], None]


async def run_skill_swarm(
    skills: Dict[str, BaseSkill],
    skill_ids: List[str],
    ctx: SkillContext,
    *,
    on_progress: Optional[SwarmProgressCallback] = None,
) -> List[Tuple[str, SkillResult, Optional[str]]]:
    """并行运行多个 Skill，返回 (skill_id, result, error) 列表。"""

    async def _one(sid: str) -> Tuple[str, SkillResult, Optional[str]]:
        skill = skills[sid]

        def skill_progress(event: str, payload: Dict[str, Any]) -> None:
            if on_progress:
                on_progress(sid, event, payload)

        result, err = await run_skill_safe(
            skill, ctx, on_progress=skill_progress if on_progress else None
        )
        return sid, result, err

    tasks = [_one(sid) for sid in skill_ids if sid in skills]
    if not tasks:
        return []
    return list(await asyncio.gather(*tasks))
