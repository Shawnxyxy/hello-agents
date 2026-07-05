"""Phase 4: Swarm / Trend / Harness Eval 测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.swarm import run_skill_swarm
from harness.eval_runner import run_safety_eval
from skills.base import BaseSkill, SkillContext, SkillResult


class _OkSkill(BaseSkill):
    def __init__(self, sid: str, summary: str):
        self.skill_id = sid
        self.description = f"skill {sid}"
        self._summary = summary

    async def run(self, ctx, on_progress=None):
        return SkillResult(skill_id=self.skill_id, success=True, summary=self._summary)


@pytest.mark.anyio
async def test_run_skill_swarm_parallel():
    skills = {
        "a": _OkSkill("a", "A ok"),
        "b": _OkSkill("b", "B ok"),
    }
    ctx = SkillContext(user_id="u1", session_id="s1", message="hi")
    results = await run_skill_swarm(skills, ["a", "b"], ctx)
    assert len(results) == 2
    assert all(r[1].success for r in results)


def test_harness_safety_eval_all_pass():
    report = run_safety_eval()
    assert report.total >= 3
    assert report.passed == report.total


def test_trend_compare_skill_skipped_without_keywords():
    from skills.trend_compare_skill import TrendCompareSkill

    skill = TrendCompareSkill()
    ctx = SkillContext(user_id="u1", session_id="s1", message="你好")
    result = asyncio.run(skill.run(ctx))
    assert result.success is False
    assert result.trace[0].get("skipped")


def test_trend_compare_skill_runs_with_keyword():
    from skills.trend_compare_skill import TrendCompareSkill

    skill = TrendCompareSkill()
    ctx = SkillContext(user_id="u1", session_id="s1", message="和上次对比趋势")
    with patch("skills.trend_compare_skill.TrendAnalysisService") as mock_svc:
        inst = mock_svc.return_value
        from models.health_trend import TrendAnalysis, TrendDirection

        inst.analyze_trends.return_value = TrendAnalysis(
            user_id="u1",
            analysis_period="90天",
            indicators_trends=[],
            overall_trend=TrendDirection.STABLE,
            summary="整体稳定",
            recommendations=["继续保持"],
            comparison_data=[],
        )
        inst.compare_with_previous.return_value = []
        result = asyncio.run(skill.run(ctx))
    assert result.success is True
    assert "稳定" in result.summary
