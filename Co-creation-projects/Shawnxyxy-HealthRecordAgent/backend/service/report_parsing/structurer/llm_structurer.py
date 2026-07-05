"""LLM 结构化补全（仅补缺失项）。"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Set

from pydantic import BaseModel, Field, ValidationError

from core.llm_adapter import get_llm_adapter
from service.report_parsing.schemas import RawIndicatorCandidate

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class LLMIndicatorItem(BaseModel):
    name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None


class LLMIndicatorBatch(BaseModel):
    indicators: List[LLMIndicatorItem] = Field(default_factory=list)


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i : j + 1])
            except json.JSONDecodeError:
                return None
    return None


async def llm_enrich_candidates(
    raw_text: str,
    existing: List[RawIndicatorCandidate],
    *,
    skip_llm: bool = False,
) -> tuple[List[RawIndicatorCandidate], bool, Optional[str]]:
    """返回 (新增候选, llm_failed, error_message)。"""
    if skip_llm:
        return [], False, None

    need_llm = len(existing) < 3 and len(raw_text.strip()) > 80
    if not need_llm:
        return [], False, None

    existing_names: Set[str] = {c.name_raw.strip().lower() for c in existing}
    text_snippet = raw_text[:6000]
    llm = get_llm_adapter()
    correction = ""
    last_err: Optional[str] = None

    for _ in range(MAX_ATTEMPTS):
        prompt = f"""
你是体检报告结构化助手。请从下列报告文本中提取**尚未出现在已有列表中**的健康指标。
已有指标（勿重复）：{json.dumps(list(existing_names), ensure_ascii=False)}

报告文本：
{text_snippet}

只返回 JSON：
{{
  "indicators": [
    {{"name": "指标名", "value": "数值或描述", "unit": "单位或null", "reference_range": "参考范围或null"}}
  ]
}}
要求：不要诊断、不要建议；最多 20 项。{correction}
"""
        try:
            resp = await llm.ainvoke(prompt)
            raw = resp.content if hasattr(resp, "content") else str(resp)
            obj = _extract_json_object(raw)
            if not obj:
                last_err = "LLM 输出无法解析为 JSON"
                correction = "\n\n【修正】请只输出合法 JSON，不要 markdown。"
                continue
            batch = LLMIndicatorBatch.model_validate(obj)
            added: List[RawIndicatorCandidate] = []
            for item in batch.indicators:
                if item.name.strip().lower() in existing_names:
                    continue
                added.append(
                    RawIndicatorCandidate(
                        name_raw=item.name.strip(),
                        value_raw=str(item.value).strip(),
                        unit_raw=item.unit,
                        reference_range=item.reference_range,
                        source="llm",
                        confidence=0.65,
                        line_context="llm",
                    )
                )
                existing_names.add(item.name.strip().lower())
            return added, False, None
        except ValidationError as exc:
            last_err = str(exc)
            correction = f"\n\n【修正】Schema 校验失败：{exc}"
        except Exception as exc:
            logger.exception("LLM 结构化失败")
            return [], True, str(exc)

    return [], True, last_err
