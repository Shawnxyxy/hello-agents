"""Skill 层基础类型与抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillContext(BaseModel):
    user_id: str
    session_id: str
    message: str = ""
    report_text: Optional[str] = None
    attachment_name: Optional[str] = None
    last_report_task_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class SkillResult(BaseModel):
    skill_id: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    degraded: bool = False


ProgressCallback = Callable[[str, Dict[str, Any]], None]


class BaseSkill(ABC):
    skill_id: str
    description: str

    @abstractmethod
    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        ...
