"""Skill 注册表。"""

from __future__ import annotations

from typing import Dict, List

from skills.base import BaseSkill
from skills.diet_recommend_skill import DietRecommendSkill
from skills.guideline_rag_skill import GuidelineRagSkill
from skills.memory_retrieve_skill import MemoryRetrieveSkill
from skills.report_analysis_skill import ReportAnalysisSkill
from skills.safety_guard_skill import SafetyGuardSkill
from skills.trend_compare_skill import TrendCompareSkill

_REGISTRY: Dict[str, BaseSkill] | None = None


def get_skill_registry() -> Dict[str, BaseSkill]:
    global _REGISTRY
    if _REGISTRY is None:
        skills: List[BaseSkill] = [
            ReportAnalysisSkill(),
            DietRecommendSkill(),
            GuidelineRagSkill(),
            MemoryRetrieveSkill(),
            SafetyGuardSkill(),
            TrendCompareSkill(),
        ]
        _REGISTRY = {s.skill_id: s for s in skills}
    return _REGISTRY


def list_skill_descriptions() -> List[Dict[str, str]]:
    return [
        {"skill_id": s.skill_id, "description": s.description}
        for s in get_skill_registry().values()
    ]
