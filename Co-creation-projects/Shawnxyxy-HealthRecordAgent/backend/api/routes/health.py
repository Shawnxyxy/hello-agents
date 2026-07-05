from uuid import uuid4
import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from memory.store import get_report_run, list_report_runs_for_user
from service.observability_views import build_report_observability
from service.health_analysis import HealthAnalysisService
from service.trend_analysis import TrendAnalysisService

router = APIRouter()


class HealthRequest(BaseModel):
    report_text: str
    user_id: str = Field(..., min_length=1, max_length=256)

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id 不能为空")
        return v


@router.post("/health/analysis")
async def analysis_health(request: HealthRequest):
    from service.report_parsing import ReportParsingPipeline
    from service.report_parsing.errors import ParseError

    task_id = str(uuid4())
    service = HealthAnalysisService(task_id=task_id, user_id=request.user_id)

    try:
        parsed = await ReportParsingPipeline().ingest_text_async(request.report_text)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    asyncio.create_task(service.run(parsed, request.user_id))

    return {
        "task_id": task_id,
        "user_id": request.user_id,
        "parse_quality": parsed.quality.model_dump(),
    }


@router.post("/health/analysis/pdf")
async def analysis_health_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    uid = user_id.strip()
    if not uid:
        return {"error": "user_id 不能为空"}

    contents = await file.read()
    from service.report_parsing import ReportParsingPipeline
    from service.report_parsing.errors import ParseError

    task_id = str(uuid4())
    service = HealthAnalysisService(task_id=task_id, user_id=uid)

    try:
        parsed = await ReportParsingPipeline().ingest_bytes_async(contents, file.filename)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    asyncio.create_task(service.run(parsed, uid))

    return {"task_id": task_id, "user_id": uid, "parse_quality": parsed.quality.model_dump()}


class ParseTextRequest(BaseModel):
    report_text: str = Field(..., min_length=1)


@router.post("/health/parse")
async def parse_report_text(body: ParseTextRequest, skip_llm: bool = True):
    """仅解析报告，不跑 Agent 流水线（调试 / 预览）。"""
    from service.report_parsing import ReportParsingPipeline
    from service.report_parsing.errors import ParseError

    try:
        parsed = await ReportParsingPipeline().ingest_text_async(
            body.report_text, skip_llm=skip_llm
        )
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return parsed.model_dump()


@router.post("/health/parse/file")
async def parse_report_file(file: UploadFile = File(...), skip_llm: bool = True):
    """上传文件，仅返回 ParsedReport。"""
    from service.report_parsing import ReportParsingPipeline
    from service.report_parsing.errors import ParseError

    contents = await file.read()
    try:
        parsed = await ReportParsingPipeline().ingest_bytes_async(
            contents, file.filename, skip_llm=skip_llm
        )
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return parsed.model_dump()


@router.get("/health/task_status/{task_id}")
async def task_status(task_id: str):
    from agents.base import get_task_status

    status = get_task_status(task_id)
    if not status:
        return {"error": "task not found"}

    return status


@router.get("/health/users/{user_id}/report_history")
async def report_history(user_id: str, limit: int = 50):
    uid = user_id.strip()
    if not uid:
        return {"error": "user_id 无效", "items": []}
    items = list_report_runs_for_user(uid, limit=limit)
    return {"user_id": uid, "items": items}


@router.get("/health/report_runs/{task_id}")
async def report_run_detail(task_id: str):
    row = get_report_run(task_id)
    if not row:
        return {"error": "未找到该次分析记录（可能尚未落库或 task_id 无效）"}
    return row


@router.get("/health/report_runs/{task_id}/observability")
async def report_run_observability(
    task_id: str, include_raw_trace: bool = False
):
    """
    阶段 3：体检分析可观测性 — 各 Agent trace 已随 report_runs 持久化（新产生任务）。
    `include_raw_trace=true` 时返回完整 trace（体积可能较大）。
    """
    row = get_report_run(task_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="未找到该次分析记录")
    return build_report_observability(row, include_raw_trace=include_raw_trace)


@router.get("/health/users/{user_id}/trend_analysis")
async def user_trend_analysis(user_id: str, period_days: int = 90):
    """历史体检趋势分析（Phase 4）。"""
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 无效")
    if period_days < 7 or period_days > 365:
        raise HTTPException(status_code=400, detail="period_days 需在 7–365 之间")

    svc = TrendAnalysisService()
    trend = await asyncio.to_thread(svc.analyze_trends, uid, period_days)
    comparisons = trend.comparison_data
    progress = await asyncio.to_thread(svc.generate_progress_report, uid, trend)

    from dataclasses import asdict

    trend_dict = asdict(trend)
    trend_dict["overall_trend"] = trend.overall_trend.value
    comp_list = []
    for c in comparisons:
        d = asdict(c)
        d["change_type"] = c.change_type.value
        comp_list.append(d)

    progress_summary = None
    if progress:
        progress_summary = {
            "report_period": progress.report_period,
            "total_reports": progress.total_reports,
            "improved_indicators": progress.improved_indicators,
            "worsened_indicators": progress.worsened_indicators,
            "overall_health_score": progress.overall_health_score,
        }

    return {
        "user_id": uid,
        "period_days": period_days,
        "trend": trend_dict,
        "latest_comparison": comp_list,
        "progress_summary": progress_summary,
    }