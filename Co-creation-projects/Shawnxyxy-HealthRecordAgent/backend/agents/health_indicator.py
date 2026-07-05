"""
健康指标分析 Agent — 解读已由解析流水线提供的结构化指标。
"""

import json
from typing import Any, Dict, List

from agents.base import BaseAgent


class HealthIndicatorAgent(BaseAgent):
    def __init__(self, task_id=None, llm=None):
        super().__init__(name="HealthIndicatorAgent", task_id=task_id, llm=llm)

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        await self.validate_input(input_data)
        self.set_state("running")

        report_text = input_data.get("report_text", "")
        pre_parsed: List[Dict[str, Any]] = input_data.get("pre_parsed_indicators") or []

        if pre_parsed:
            indicators = await self._interpret_indicators(pre_parsed, report_text)
        else:
            indicators = await self._extract_from_text(report_text)

        self.set_state("completed")
        return {"indicators": indicators}

    async def _interpret_indicators(
        self, pre_parsed: List[Dict[str, Any]], report_text: str
    ) -> List[Dict[str, Any]]:
        prompt = f"""
你是一名专业的健康分析助手。以下指标已由系统从体检报告中结构化提取，请为每项补充 status、risk_level、analysis。
不要新增报告中不存在的指标，不要修改数值。

已提取指标：
{json.dumps(pre_parsed, ensure_ascii=False, indent=2)}

报告原文（供参考）：
{report_text[:3000]}

返回 JSON：
{{
  "indicators": [
    {{
      "name": "展示名",
      "canonical_code": "标准code或null",
      "value": "原值",
      "unit": "单位",
      "status": "normal|borderline|high|low|abnormal|unknown",
      "risk_level": "low|medium|high",
      "analysis": "简要含义"
    }}
  ]
}}
"""
        response = await self.think(prompt)
        try:
            result = json.loads(response)
            items = result.get("indicators", [])
            if isinstance(items, list) and items:
                return items
        except json.JSONDecodeError:
            pass
        return self._fallback_from_pre_parsed(pre_parsed)

    def _fallback_from_pre_parsed(self, pre_parsed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in pre_parsed:
            out.append(
                {
                    "name": item.get("name") or item.get("display_name"),
                    "canonical_code": item.get("canonical_code"),
                    "value": item.get("value"),
                    "normalized_value": item.get("normalized_value"),
                    "unit": item.get("unit", ""),
                    "status": item.get("status") or "unknown",
                    "risk_level": "low",
                    "analysis": "已由解析流水线提取，待进一步解读。",
                    "needs_review": item.get("needs_review", False),
                }
            )
        return out

    async def _extract_from_text(self, report_text: str) -> List[Dict[str, Any]]:
        prompt = f"""
你是一名专业的健康分析助手。
请从以下体检或健康报告中提取关键健康指标，并判断风险。

报告内容：
{report_text}

请返回 JSON，严格遵循以下格式：
{{
  "indicator_results": {{
    "<指标名>": {{
      "value": "<原始数值或描述>",
      "status": "<normal | borderline | high | low | abnormal>",
      "risk_level": "<low | medium | high>",
      "analysis": "<简要分析该指标的健康含义>"
    }}
  }}
}}
"""
        response = await self.think(prompt)
        indicators: List[Dict[str, Any]] = []
        try:
            result = json.loads(response)
            indicator_dict = result.get("indicator_results", {})
            for name, data in indicator_dict.items():
                indicators.append(
                    {
                        "name": name,
                        "value": data.get("value"),
                        "status": data.get("status"),
                        "risk_level": data.get("risk_level"),
                        "analysis": data.get("analysis"),
                    }
                )
        except json.JSONDecodeError:
            indicators = []
        return indicators

    def get_required_fields(self) -> List[str]:
        return []
