"""医疗场景 Harness 安全规则。"""

from __future__ import annotations

import re
from typing import List, Tuple

DISCLAIMER = (
    "【免责声明】以上内容为健康参考信息，不能替代专业医疗诊断与治疗。"
    "如有不适或症状加重，请及时就医。"
)

HIGH_RISK_PATTERNS: List[Tuple[str, str]] = [
    (r"胸痛|胸口.{0,4}痛|心绞痛", "检测到胸痛相关描述"),
    (r"意识模糊|昏迷|晕厥|不省人事", "检测到意识障碍相关描述"),
    (r"大量出血|咯血|呕血|便血", "检测到出血相关描述"),
    (r"呼吸困难|喘不上气|窒息", "检测到呼吸窘迫相关描述"),
    (r"突发.{0,6}偏瘫|口眼歪斜|言语不清", "检测到卒中警示症状"),
]

FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
    (r"你(得了|患了|确诊为)", "避免给出明确诊断"),
    (r"每天.{0,8}片|每次.{0,8}mg|剂量.{0,8}mg", "避免推荐具体药物剂量"),
]


def detect_high_risk(text: str) -> List[str]:
    flags: List[str] = []
    for pattern, label in HIGH_RISK_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            flags.append(label)
    return flags


def detect_forbidden_output(text: str) -> List[str]:
    issues: List[str] = []
    for pattern, label in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            issues.append(label)
    return issues


def ensure_disclaimer(text: str) -> str:
    if DISCLAIMER[:8] in text:
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER}"


def build_urgent_care_notice(flags: List[str]) -> str:
    if not flags:
        return ""
    reasons = "；".join(flags)
    return (
        f"⚠️ **紧急提醒**：根据你的描述（{reasons}），"
        "这类情况可能较为严重，建议尽快前往医院急诊或拨打 120，"
        "不要仅依赖线上建议延误就医。\n\n"
    )
