"""Code Review Important #14–#19 修复验证。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from chat.orchestrator import HealthAssistantOrchestrator
from chat.swarm import run_skill_swarm
from models.health_trend import TrendAnalysis, TrendDirection
from service.trend_analysis import TrendAnalysisService
from skills.base import BaseSkill, SkillContext, SkillResult


class _SummaryOnlySkill(BaseSkill):
    skill_id = "trend_compare"
    description = "mock trend"

    async def run(self, ctx, on_progress=None):
        if on_progress:
            on_progress("skill_progress", {"stage": "analyze", "status": "running"})
        return SkillResult(
            skill_id=self.skill_id,
            success=False,
            summary="数据不足，无法进行趋势分析。",
            trace=[{"skipped": False}],
            degraded=True,
        )


class _ProgressSkill(BaseSkill):
    skill_id = "memory_retrieve"
    description = "mock memory"

    async def run(self, ctx, on_progress=None):
        if on_progress:
            on_progress("skill_progress", {"stage": "retrieve", "status": "running"})
        return SkillResult(skill_id=self.skill_id, success=True, summary="mem ok")


@pytest.mark.anyio
async def test_swarm_forwards_progress():
    progress_events = []

    def on_progress(sid, event, payload):
        progress_events.append((sid, event, payload))

    skills = {"memory_retrieve": _ProgressSkill()}
    ctx = SkillContext(user_id="u1", session_id="s1", message="hi")
    await run_skill_swarm(skills, ["memory_retrieve"], ctx, on_progress=on_progress)
    assert any(e[1] == "skill_progress" for e in progress_events)


def test_parse_created_at_handles_bad_and_z_suffix():
    svc = TrendAnalysisService()
    assert svc._parse_created_at("2024-01-15T10:00:00+00:00") is not None
    assert svc._parse_created_at("2024-01-15T10:00:00Z") is not None
    assert svc._parse_created_at("not-a-date") is None
    assert svc._parse_created_at("") is None


def test_analyze_trends_skips_bad_dates():
    svc = TrendAnalysisService()
    reports = [
        MagicMock(created_at="bad", indicators=[]),
        MagicMock(created_at="also-bad", indicators=[]),
    ]
    with patch.object(svc, "get_user_reports", return_value=reports):
        trend = svc.analyze_trends("u1", 90)
    assert trend.overall_trend == TrendDirection.UNKNOWN
    assert "数据不足" in trend.summary


def test_generate_progress_report_reuses_trend():
    svc = TrendAnalysisService()
    precomputed = TrendAnalysis(
        user_id="u1",
        analysis_period="90天",
        indicators_trends=[{"indicator_name": "血糖", "trend": "stable"}],
        overall_trend=TrendDirection.STABLE,
        summary="稳定",
        recommendations=["继续保持"],
        comparison_data=[],
    )
    fake_reports = [
        MagicMock(created_at="2024-06-01T00:00:00+00:00", indicators=[]),
        MagicMock(created_at="2024-01-01T00:00:00+00:00", indicators=[]),
    ]
    with patch.object(svc, "get_user_reports", return_value=fake_reports):
        with patch.object(svc, "analyze_trends") as mock_analyze:
            progress = svc.generate_progress_report("u1", precomputed)
            mock_analyze.assert_not_called()
    assert progress is not None
    assert progress.trend_analysis is precomputed


@pytest.mark.anyio
async def test_orchestrator_includes_degraded_trend_summary():
    """#14: success=False 但有 summary 的 trend 应进入 skill_results。"""
    orch = HealthAssistantOrchestrator()
    degraded = SkillResult(
        skill_id="trend_compare",
        success=False,
        summary="数据不足，无法进行趋势分析。",
        degraded=True,
    )
    noop = SkillResult(skill_id="noop", success=True, summary="")

    registry = {
        "memory_retrieve": _ProgressSkill(),
        "guideline_rag": _ProgressSkill(),
        "trend_compare": _SummaryOnlySkill(),
        "safety_guard": MagicMock(),
    }

    with patch("chat.orchestrator.get_chat_session", return_value={"user_id": "u1", "last_report_task_id": None}), \
         patch("chat.orchestrator.append_chat_message", return_value=1), \
         patch("chat.orchestrator.list_chat_messages", return_value=[]), \
         patch("chat.orchestrator.get_skill_registry", return_value=registry), \
         patch("chat.orchestrator.run_skill_swarm", return_value=[
             ("memory_retrieve", noop, None),
             ("guideline_rag", noop, None),
             ("trend_compare", degraded, None),
         ]), \
         patch("chat.orchestrator.get_llm_adapter") as mock_llm, \
         patch("chat.orchestrator.run_skill_safe") as mock_safe:
        captured_prompts = []

        class FakeLLM:
            async def ainvoke(self, messages):
                captured_prompts.append(messages)
                return "回复"

        mock_llm.return_value = FakeLLM()
        mock_safe.return_value = (
            SkillResult(skill_id="safety_guard", success=True, data={"text": "回复"}),
            None,
        )

        async for _ in orch.stream_response("s1", "u1", "对比趋势"):
            pass

    user_prompt = captured_prompts[0][1]["content"]
    assert "数据不足" in user_prompt


def test_trend_api_period_days_validation():
    from api.routes.health import user_trend_analysis

    with pytest.raises(HTTPException) as exc:
        asyncio.run(user_trend_analysis("u1", period_days=3))
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        asyncio.run(user_trend_analysis("u1", period_days=400))
    assert exc.value.status_code == 400
