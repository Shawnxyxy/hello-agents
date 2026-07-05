"""体检报告分析 Skill — Parse → Analyze 两阶段。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agents.base import get_task_status
from service.health_analysis import HealthAnalysisService
from service.report_parsing import ParsedReport, ReportParsingPipeline
from service.report_parsing.errors import ParseError
from skills.base import BaseSkill, ProgressCallback, SkillContext, SkillResult

logger = logging.getLogger(__name__)

AGENT_LABELS = {
    "ReportParsing": "解析体检报告",
    "PlannerAgent": "规划分析步骤",
    "HealthIndicatorAgent": "解读健康指标",
    "RiskAssessmentAgent": "评估健康风险",
    "AdviceAgent": "生成健康建议",
    "ReportAgent": "汇总分析报告",
}


def _read_agent_state(agents: Dict[str, Any], agent_key: str) -> str:
    raw = agents.get(agent_key)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return str(raw.get("status") or "")
    return ""


def extract_report_inner(task_status: Dict[str, Any]) -> Dict[str, Any]:
    raw = task_status.get("report")
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("report")
    if isinstance(inner, dict):
        return inner
    return raw


def build_report_summary(inner: Dict[str, Any], parse_quality: Optional[Dict[str, Any]] = None) -> str:
    parts: List[str] = []
    if parse_quality:
        score = parse_quality.get("overall_score")
        count = parse_quality.get("indicator_count")
        if score is not None:
            parts.append(f"解析置信度 {float(score) * 100:.0f}%")
        if count is not None:
            parts.append(f"结构化指标 {count} 项")

    if inner.get("summary"):
        parts.append(str(inner["summary"])[:400])

    risk = inner.get("risk_section") or inner.get("risk_assessment") or {}
    if isinstance(risk, dict) and risk.get("overall_risk_level"):
        parts.append(f"综合风险等级：{risk['overall_risk_level']}")

    indicators = inner.get("indicator_section") or inner.get("indicators") or inner.get("indicator_results")
    if isinstance(indicators, list) and indicators:
        parts.append(f"分析指标 {len(indicators)} 项")

    advice = inner.get("advice_section") or inner.get("advice")
    if isinstance(advice, list) and advice:
        parts.append(f"健康建议 {len(advice)} 条")

    return "；".join(parts) if parts else "体检报告分析已完成，详见结构化结果。"


class ReportAnalysisSkill(BaseSkill):
    skill_id = "report_analysis"
    description = "解析并分析用户上传的体检报告（文本或 PDF），输出结构化解读与建议。"

    async def run(
        self,
        ctx: SkillContext,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SkillResult:
        report_text = (ctx.report_text or "").strip()
        file_bytes = ctx.extra.get("attachment_bytes")
        filename = ctx.attachment_name

        if not report_text and not file_bytes:
            return SkillResult(
                skill_id=self.skill_id,
                success=False,
                summary="未提供可分析的体检报告内容。",
                trace=[{"error": "empty_report_text"}],
            )

        trace: list[Dict[str, Any]] = []
        parsed: Optional[ParsedReport] = ctx.extra.get("parsed_report")
        if isinstance(parsed, dict):
            parsed = ParsedReport.model_validate(parsed)

        if parsed is None:
            if on_progress:
                on_progress(
                    "skill_progress",
                    {
                        "skill": self.skill_id,
                        "stage": "ReportParsing",
                        "label": AGENT_LABELS["ReportParsing"],
                        "status": "running",
                    },
                )
            pipeline = ReportParsingPipeline()
            try:
                if file_bytes:
                    parsed = await pipeline.ingest_bytes_async(file_bytes, filename)
                else:
                    parsed = await pipeline.ingest_text_async(report_text, filename or "report.txt")
            except ParseError as exc:
                return SkillResult(
                    skill_id=self.skill_id,
                    success=False,
                    summary=str(exc),
                    trace=[{"stage": "ReportParsing", "error": exc.code.value}],
                )
            trace.append(
                {
                    "stage": "ReportParsing",
                    "status": "completed",
                    "indicator_count": parsed.quality.indicator_count,
                    "quality_score": parsed.quality.overall_score,
                }
            )
            if on_progress:
                on_progress(
                    "skill_progress",
                    {
                        "skill": self.skill_id,
                        "stage": "ReportParsing",
                        "label": AGENT_LABELS["ReportParsing"],
                        "status": "completed",
                    },
                )

        if parsed.quality.indicator_count == 0 and parsed.quality.degraded:
            return SkillResult(
                skill_id=self.skill_id,
                success=False,
                summary="未能从报告中识别到有效指标，请检查文件格式或换用文字版报告。",
                data={"parsed_report": parsed.model_dump()},
                trace=trace,
                degraded=True,
            )

        task_id = str(uuid4())
        service = HealthAnalysisService(task_id=task_id, user_id=ctx.user_id)
        seen_running: set[str] = set()
        seen_completed: set[str] = set()

        async def _run_pipeline() -> None:
            await service.run(parsed, ctx.user_id)

        pipeline_task = asyncio.create_task(_run_pipeline())

        while not pipeline_task.done():
            status = get_task_status(task_id) or {}
            agents = status.get("agents") or {}
            for agent_key, label in AGENT_LABELS.items():
                if agent_key == "ReportParsing":
                    continue
                state = _read_agent_state(agents, agent_key)
                if state == "running" and agent_key not in seen_running:
                    seen_running.add(agent_key)
                    if on_progress:
                        on_progress(
                            "skill_progress",
                            {
                                "skill": self.skill_id,
                                "stage": agent_key,
                                "label": label,
                                "status": "running",
                            },
                        )
                if state == "completed" and agent_key not in seen_completed:
                    seen_completed.add(agent_key)
                    trace.append({"agent": agent_key, "status": "completed"})
                    if on_progress:
                        on_progress(
                            "skill_progress",
                            {
                                "skill": self.skill_id,
                                "stage": agent_key,
                                "label": label,
                                "status": "completed",
                            },
                        )
            await asyncio.sleep(0.4)

        await pipeline_task
        status = get_task_status(task_id) or {}
        inner = extract_report_inner(status)
        task_report = status.get("report") if isinstance(status.get("report"), dict) else {}
        success = status.get("state") == "completed" and bool(inner or task_report)

        if pipeline_task.exception():
            logger.exception("报告分析流水线失败", exc_info=pipeline_task.exception())
            return SkillResult(
                skill_id=self.skill_id,
                success=False,
                data={"task_id": task_id, "parsed_report": parsed.model_dump()},
                summary="体检报告分析失败，请稍后重试。",
                trace=trace + [{"error": str(pipeline_task.exception())}],
                degraded=True,
            )

        summary = build_report_summary(inner, parsed.quality.model_dump())

        return SkillResult(
            skill_id=self.skill_id,
            success=success,
            data={
                "task_id": task_id,
                "report": task_report,
                "report_inner": inner,
                "parsed_report": parsed.model_dump(),
            },
            summary=summary,
            trace=trace,
            degraded=not success or parsed.quality.degraded,
        )
