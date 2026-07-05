"""健康助手对话编排器 — Skills-Agent 两层架构。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator, Dict, List, Optional

from chat.report_context import build_prior_report_context
from core.exceptions import LLMException
from core.llm_adapter import get_llm_adapter
from memory.store import (
    append_chat_message,
    get_chat_session,
    list_chat_messages,
    touch_chat_session,
)
from chat.skill_runner import run_skill_safe
from chat.swarm import run_skill_swarm
from skills.base import BaseSkill, SkillContext, SkillResult
from skills.registry import get_skill_registry

DIET_PATTERN = re.compile(r"吃|饮食|餐|热量|蛋白|减脂|增肌|早餐|午餐|晚餐|零食|营养")
TREND_PATTERN = re.compile(r"对比|上次|趋势|变化|改善|恶化|进步|历史报告|比一下|有没有好转")

logger = logging.getLogger(__name__)


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chunk_text_for_stream(text: str, chunk_size: int = 24) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


async def _drain_progress_queue(
    queue: asyncio.Queue[tuple[str, Dict[str, Any]]],
) -> AsyncIterator[str]:
    while not queue.empty():
        evt, payload = queue.get_nowait()
        yield _sse(evt, payload)


async def _run_skill_with_live_progress(
    skill: BaseSkill,
    ctx: SkillContext,
    *,
    start_label: str,
) -> AsyncIterator[str | SkillResult]:
    """实时推送 on_progress 事件，最后一项为 SkillResult。"""
    yield _sse("skill_start", {"skill": skill.skill_id, "label": start_label})

    progress_queue: asyncio.Queue[tuple[str, Dict[str, Any]]] = asyncio.Queue()

    def on_progress(event: str, payload: Dict[str, Any]) -> None:
        progress_queue.put_nowait((event, payload))

    skill_task = asyncio.create_task(run_skill_safe(skill, ctx, on_progress=on_progress))

    while not skill_task.done():
        async for chunk in _drain_progress_queue(progress_queue):
            yield chunk
        await asyncio.sleep(0.05)

    async for chunk in _drain_progress_queue(progress_queue):
        yield chunk

    result, error = await skill_task
    if error:
        yield _sse("error", {"skill": skill.skill_id, "message": error})
    yield _sse("skill_progress", {"skill": skill.skill_id, "status": "completed"})
    yield result


class HealthAssistantOrchestrator:
    async def stream_response(
        self,
        session_id: str,
        user_id: str,
        message: str,
        *,
        report_text: Optional[str] = None,
        attachment_name: Optional[str] = None,
        attachment_bytes: Optional[bytes] = None,
    ) -> AsyncIterator[str]:
        session = await asyncio.to_thread(get_chat_session, session_id)
        if not session or session["user_id"] != user_id:
            yield _sse("error", {"message": "会话不存在或 user_id 不匹配"})
            return

        user_content = message.strip()
        if attachment_name and (report_text or attachment_bytes):
            user_content = user_content or f"[上传附件: {attachment_name}]"

        await asyncio.to_thread(
            append_chat_message,
            session_id,
            "user",
            user_content,
            attachment_name=attachment_name,
        )

        registry = get_skill_registry()
        ctx = SkillContext(
            user_id=user_id,
            session_id=session_id,
            message=message.strip(),
            report_text=report_text,
            attachment_name=attachment_name,
            last_report_task_id=session.get("last_report_task_id"),
            extra={"attachment_bytes": attachment_bytes} if attachment_bytes else {},
        )

        skill_results: List[SkillResult] = []
        orchestrator_trace: List[Dict[str, Any]] = []

        report_result: Optional[SkillResult] = None
        has_report = bool((report_text and report_text.strip()) or attachment_bytes)
        if has_report:
            async for item in _run_skill_with_live_progress(
                registry["report_analysis"],
                ctx,
                start_label="体检报告分析",
            ):
                if isinstance(item, SkillResult):
                    report_result = item
                else:
                    yield item

            if report_result:
                skill_results.append(report_result)
                orchestrator_trace.append(
                    {"skill": "report_analysis", "success": report_result.success}
                )
                parsed_payload = report_result.data.get("parsed_report")
                if isinstance(parsed_payload, dict) and parsed_payload.get("quality"):
                    q = parsed_payload["quality"]
                    yield _sse(
                        "parse_quality",
                        {
                            "overall_score": q.get("overall_score"),
                            "indicator_count": q.get("indicator_count"),
                            "low_confidence_count": q.get("low_confidence_count"),
                            "degraded": q.get("degraded"),
                            "extraction_method": q.get("extraction_method"),
                            "warnings": (q.get("warnings") or [])[:3],
                        },
                    )
                if report_result.success and report_result.data.get("task_id"):
                    await asyncio.to_thread(
                        touch_chat_session,
                        session_id,
                        last_report_task_id=report_result.data["task_id"],
                    )
                    ctx.last_report_task_id = report_result.data["task_id"]
                    ctx = ctx.model_copy(update={"extra": {**ctx.extra, "force_trend": True}})

        elif ctx.last_report_task_id:
            prior = await asyncio.to_thread(
                build_prior_report_context, ctx.last_report_task_id, user_id
            )
            if prior:
                skill_results.append(prior)
                orchestrator_trace.append(
                    {"skill": "prior_report_context", "success": True}
                )
                yield _sse(
                    "skill_progress",
                    {
                        "skill": "prior_report_context",
                        "label": "加载已分析报告",
                        "status": "completed",
                    },
                )

        swarm_ids = ["memory_retrieve", "guideline_rag"]
        if ctx.extra.get("force_trend") or TREND_PATTERN.search(message):
            swarm_ids.append("trend_compare")

        yield _sse("skill_start", {"skill": "agent_swarm", "label": f"并行执行 {len(swarm_ids)} 个 Skill"})
        swarm_labels = {
            "memory_retrieve": "记忆检索",
            "guideline_rag": "指南检索",
            "trend_compare": "趋势分析",
        }
        for sid in swarm_ids:
            yield _sse("skill_start", {"skill": sid, "label": swarm_labels.get(sid, sid)})

        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        def on_swarm_progress(sid: str, event: str, payload: Dict[str, Any]) -> None:
            progress_queue.put_nowait(_sse(event, {**payload, "skill": sid}))

        swarm_task = asyncio.create_task(
            run_skill_swarm(registry, swarm_ids, ctx, on_progress=on_swarm_progress)
        )
        while not swarm_task.done():
            while not progress_queue.empty():
                yield progress_queue.get_nowait()
            await asyncio.sleep(0.05)
        while not progress_queue.empty():
            yield progress_queue.get_nowait()

        swarm_results = await swarm_task
        for sid, result, err in swarm_results:
            if err:
                yield _sse("error", {"skill": sid, "message": err})
            yield _sse("skill_progress", {"skill": sid, "status": "completed"})
            if result.success or sid in ("memory_retrieve", "guideline_rag") or result.summary.strip():
                skill_results.append(result)
            orchestrator_trace.append({"skill": sid, "success": result.success, "swarm": True})

        if DIET_PATTERN.search(message):
            yield _sse("skill_start", {"skill": "diet_recommend", "label": "饮食建议"})
            diet_result, diet_err = await run_skill_safe(registry["diet_recommend"], ctx)
            if diet_err:
                yield _sse("error", {"skill": "diet_recommend", "message": diet_err})
            if diet_result.success:
                skill_results.append(diet_result)
                orchestrator_trace.append({"skill": "diet_recommend", "success": True})
            else:
                orchestrator_trace.append({"skill": "diet_recommend", "success": False})
            yield _sse("skill_progress", {"skill": "diet_recommend", "status": "completed"})

        history = await asyncio.to_thread(list_chat_messages, session_id, 20)
        history_text = "\n".join(
            f"{m['role']}: {m['content'][:500]}" for m in history[:-1]
        )

        skill_context_block = "\n\n".join(
            f"【{r.skill_id}】\n{r.summary}" for r in skill_results if r.summary
        )

        system_prompt = (
            "你是「健康助手」，一位谨慎、专业的健康管理 AI。"
            "你不能给出明确疾病诊断，不能推荐具体药物剂量。"
            "请基于以下 Skill 结果与用户对话，用清晰、分点的中文回答。"
            "若信息不足，请主动追问。"
        )
        user_prompt = (
            f"对话历史（最近）：\n{history_text or '（无）'}\n\n"
            f"用户本轮消息：\n{message.strip() or '（仅上传附件）'}\n\n"
            f"Skill 结果摘要：\n{skill_context_block or '（无）'}\n\n"
            "请生成给用户的回复正文（不要重复免责声明，系统会自动附加）。"
        )

        llm = get_llm_adapter()
        try:
            draft = await llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except LLMException as exc:
            logger.exception("LLM 调用失败: %s", exc)
            draft = (
                "抱歉，模型服务暂时不可用，请稍后再试。\n\n"
                f"已完成的 Skill 摘要：\n{skill_context_block or '（无）'}"
            )
            orchestrator_trace.append({"skill": "llm", "success": False, "error": str(exc)})

        safety_ctx = SkillContext(
            user_id=user_id,
            session_id=session_id,
            message=message.strip(),
            extra={"draft_response": draft},
        )
        safety_result, safety_err = await run_skill_safe(registry["safety_guard"], safety_ctx)
        if safety_err:
            yield _sse("error", {"skill": "safety_guard", "message": safety_err})
        final_text = safety_result.data.get("text") or draft
        orchestrator_trace.append({"skill": "safety_guard", "modified": safety_result.data.get("modified")})

        if safety_result.data.get("high_risk_flags"):
            yield _sse("safety", {"flags": safety_result.data["high_risk_flags"]})

        for chunk in _chunk_text_for_stream(final_text):
            yield _sse("token", {"text": chunk})
            await asyncio.sleep(0.02)

        msg_id = await asyncio.to_thread(
            append_chat_message,
            session_id,
            "assistant",
            final_text,
            trace={"skills": orchestrator_trace, "skill_summaries": [r.model_dump() for r in skill_results]},
        )

        yield _sse(
            "done",
            {
                "message_id": msg_id,
                "text": final_text,
                "trace": orchestrator_trace,
                "parse_quality": (
                    report_result.data.get("parsed_report", {}).get("quality")
                    if report_result and isinstance(report_result.data.get("parsed_report"), dict)
                    else None
                ),
            },
        )
