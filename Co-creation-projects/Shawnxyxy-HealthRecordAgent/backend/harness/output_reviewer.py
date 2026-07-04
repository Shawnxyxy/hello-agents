"""Harness 输出审查。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from harness.safety_rules import (
    build_urgent_care_notice,
    detect_forbidden_output,
    detect_high_risk,
    ensure_disclaimer,
)


@dataclass
class ReviewResult:
    text: str
    high_risk_flags: List[str]
    forbidden_issues: List[str]
    modified: bool


def review_assistant_output(user_input: str, assistant_output: str) -> ReviewResult:
    high_risk = detect_high_risk(user_input) + detect_high_risk(assistant_output)
    forbidden = detect_forbidden_output(assistant_output)

    text = assistant_output
    modified = False

    urgent = build_urgent_care_notice(high_risk)
    if urgent and urgent not in text:
        text = urgent + text
        modified = True

    if forbidden:
        text = (
            "关于具体诊断或用药剂量，我无法在线上给出确定结论。"
            "建议你携带检查资料咨询正规医疗机构。\n\n" + text
        )
        modified = True

    final = ensure_disclaimer(text)
    if final != text:
        modified = True
        text = final

    return ReviewResult(
        text=text,
        high_risk_flags=high_risk,
        forbidden_issues=forbidden,
        modified=modified,
    )
