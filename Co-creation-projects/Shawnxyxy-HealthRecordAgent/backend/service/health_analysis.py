"""
健康分析工作流服务
负责串联多个 Agent，完成一次完整的健康报告分析
"""

import asyncio
import logging
from typing import Any, Dict, Union
from uuid import uuid4

from agents.planner import PlannerAgent
from agents.health_indicator import HealthIndicatorAgent
from agents.risk_assess import RiskAssessmentAgent
from agents.advice import AdviceAgent
from agents.report import ReportAgent
from agents.base import create_task, update_agent_state, complete_task
from memory.store import save_completed_report_run
from rag.indexers import index_report_run
from rag.retriever import retrieve
from service.report_parsing.schemas import ParsedReport

logger = logging.getLogger(__name__)


def _indicator_list_from_agent_result(indicator_result: Any) -> list[Dict[str, Any]]:
    """HealthIndicatorAgent 返回 {"indicators": [...]}，ReportAgent 需要 list。"""
    if isinstance(indicator_result, list):
        return indicator_result
    if isinstance(indicator_result, dict):
        items = indicator_result.get("indicators")
        if isinstance(items, list):
            return items
    return []


class HealthAnalysisService:
    def __init__(self, task_id: str | None = None, user_id: str | None = None):
        self.task_id = task_id or str(uuid4())
        self.user_id = user_id
        # 任务初始化
        create_task(self.task_id, user_id=user_id)

        self.planner = PlannerAgent(task_id=self.task_id)
        self.indicator_agent = HealthIndicatorAgent(task_id=self.task_id)
        self.risk_agent = RiskAssessmentAgent(task_id=self.task_id)
        self.advice_agent = AdviceAgent(task_id=self.task_id)
        self.report_agent = ReportAgent(task_id=self.task_id)

    def _bundle_agent_traces(self, limit_per_agent: int = 80) -> Dict[str, Any]:
        """阶段 3：各 Agent 的 trace 切片落库。"""
        pairs = [
            ("PlannerAgent", self.planner),
            ("HealthIndicatorAgent", self.indicator_agent),
            ("RiskAssessmentAgent", self.risk_agent),
            ("AdviceAgent", self.advice_agent),
            ("ReportAgent", self.report_agent),
        ]
        out: Dict[str, Any] = {}
        for name, ag in pairs:
            try:
                t = ag.get_traces()
                out[name] = t[-limit_per_agent:] if len(t) > limit_per_agent else list(t)
            except Exception:
                out[name] = []
        return out

    async def run(self, report_input: Union[str, ParsedReport], user_id: str) -> Dict[str, Any]:
        """
        执行完整的健康分析流程。
        report_input: 纯文本（legacy）或 ParsedReport（解析流水线输出）。
        """
        parsed_meta: Dict[str, Any] | None = None
        pre_parsed: list[Dict[str, Any]] | None = None

        if isinstance(report_input, ParsedReport):
            report_text = report_input.artifact.raw_text
            pre_parsed = report_input.to_agent_indicators()
            parsed_meta = report_input.model_dump()
        else:
            report_text = str(report_input)

        # 1.任务规划
        update_agent_state(self.task_id, "PlannerAgent", "running")
        plan_result = await self.planner.run({"goal": f"分析以下体检报告并制定执行计划：\n{report_text}"})
        update_agent_state(self.task_id, "PlannerAgent", "completed")

        # 2.健康指标分析
        update_agent_state(self.task_id, "HealthIndicatorAgent", "running")
        indicator_result = await self.indicator_agent.run({
            "report_text": report_text,
            "plan": plan_result,
            "pre_parsed_indicators": pre_parsed,
        })
        update_agent_state(self.task_id, "HealthIndicatorAgent", "completed", partial_report={"indicator_results": indicator_result})

        # 3. 风险评估
        update_agent_state(self.task_id, "RiskAssessmentAgent", "running")
        risk_result = await self.risk_agent.run({
            "indicator_results": indicator_result
        })
        update_agent_state(self.task_id, "RiskAssessmentAgent", "completed", partial_report={"risk_assessment": risk_result})

        rag_result = await asyncio.to_thread(
            retrieve,
            user_id,
            {
                "scenario": "health_report_analysis",
                "risk_focus": str(risk_result.get("overall_risk_level", "")),
                "query": "历史体检变化与执行反馈",
            },
        )
        retrieved_memory = rag_result.get("summary", "（暂无召回记忆）")

        # 4. 健康建议生成
        update_agent_state(self.task_id, "AdviceAgent", "running")
        advice_result = await self.advice_agent.run({
            "risk_assessment": risk_result,
            "retrieved_memory": retrieved_memory,
        })
        update_agent_state(self.task_id, "AdviceAgent", "completed", partial_report={"advice": advice_result})


        # 5. 报告汇总
        update_agent_state(self.task_id, "ReportAgent", "running")
        final_report = await self.report_agent.run({
            "indicators": _indicator_list_from_agent_result(indicator_result),
            "risk_assessment": risk_result,
            "advice": advice_result,
            "retrieved_memory": retrieved_memory,
        })
        if parsed_meta:
            inner = final_report.get("report") if isinstance(final_report.get("report"), dict) else final_report
            if isinstance(inner, dict):
                inner["parsed_report_meta"] = {
                    "schema_version": parsed_meta.get("schema_version"),
                    "quality": parsed_meta.get("quality"),
                    "raw_text_hash": parsed_meta.get("raw_text_hash"),
                }
        update_agent_state(self.task_id, "ReportAgent", "completed")
        complete_task(self.task_id, final_report)

        try:
            traces = self._bundle_agent_traces()
            await asyncio.to_thread(
                save_completed_report_run,
                user_id,
                self.task_id,
                final_report,
                traces,
            )
        except Exception as e:
            logger.exception("写入 SQLite 履历失败（分析结果仍有效）: %s", e)
        try:
            await asyncio.to_thread(index_report_run, self.task_id)
        except Exception as e:
            logger.warning("report run 向量索引失败（不影响返回）: %s", e)

        return self.task_id

# ---------- 临时本地验证入口 ----------

async def _demo():
    demo_text = """
        男性，28岁，BMI 27.3，血压 145/95 mmHg，
        总胆固醇 6.2 mmol/L，空腹血糖 6.1 mmol/L。
        """

    workflow = HealthAnalysisService(user_id="local-demo-user")
    result = await workflow.run(demo_text, user_id="local-demo-user")
    print(result)

if __name__ == "__main__":
    asyncio.run(_demo())
