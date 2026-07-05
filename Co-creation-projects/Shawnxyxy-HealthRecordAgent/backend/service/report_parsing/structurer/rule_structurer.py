"""规则结构化：表格 + 正则。"""

from __future__ import annotations

import re
from typing import List

from service.report_parsing.schemas import DocumentArtifact, PatientMeta, RawIndicatorCandidate


_LINE_PATTERN = re.compile(
    r"^[\s\-•]*(.{2,24}?)[：:\s]+([\d./]+(?:\s*[a-zA-Zμ/²³%·]+)?)\s*(.*)?$",
    re.MULTILINE,
)
_NAME_PATTERN = re.compile(r"姓名[：:]\s*(\S+)")
_SEX_PATTERN = re.compile(r"性别[：:]\s*(\S+)")
_AGE_PATTERN = re.compile(r"年龄[：:]\s*(\d+)")


def _extract_patient(text: str) -> PatientMeta | None:
    name = _NAME_PATTERN.search(text)
    sex = _SEX_PATTERN.search(text)
    age = _AGE_PATTERN.search(text)
    if not any([name, sex, age]):
        return None
    return PatientMeta(
        name=name.group(1) if name else None,
        sex=sex.group(1) if sex else None,
        age=int(age.group(1)) if age else None,
    )


def _first_patient_block(text: str) -> tuple[str, list[str]]:
    """多人报告取第一块，并返回 warnings。"""
    warnings: list[str] = []
    blocks = re.split(r"(?=姓名[：:])", text)
    blocks = [b.strip() for b in blocks if b.strip()]
    if len(blocks) > 1:
        warnings.append("检测到多份报告，已默认解析第一段")
        return blocks[0], warnings
    return text, warnings


def _from_tables(artifact: DocumentArtifact) -> List[RawIndicatorCandidate]:
    out: List[RawIndicatorCandidate] = []
    for table in artifact.tables:
        for row in table:
            if len(row) < 2:
                continue
            name = row[0].strip()
            value = row[1].strip()
            if not name or not value or not re.search(r"\d", value):
                continue
            unit = row[2].strip() if len(row) > 2 else None
            ref = row[3].strip() if len(row) > 3 else None
            out.append(
                RawIndicatorCandidate(
                    name_raw=name,
                    value_raw=value,
                    unit_raw=unit or None,
                    reference_range=ref or None,
                    source="table",
                    confidence=0.88,
                    line_context=" | ".join(row[:4]),
                )
            )
    return out


def _from_regex(text: str) -> List[RawIndicatorCandidate]:
    out: List[RawIndicatorCandidate] = []
    for m in _LINE_PATTERN.finditer(text):
        name = m.group(1).strip()
        value = m.group(2).strip()
        tail = (m.group(3) or "").strip()
        if len(name) < 2:
            continue
        if name in ("姓名", "性别"):
            continue
        unit = None
        unit_m = re.search(r"([a-zA-Zμ/%²³·]+(?:/L|/dL|mmHg|次/分钟)?)", tail)
        if unit_m:
            unit = unit_m.group(1)
        out.append(
            RawIndicatorCandidate(
                name_raw=name,
                value_raw=value,
                unit_raw=unit,
                source="regex",
                confidence=0.82,
                line_context=m.group(0).strip(),
            )
        )

    bp = re.search(r"血压[：:\s]*(\d{2,3})\s*[/／]\s*(\d{2,3})\s*(mmHg)?", text)
    if bp:
        out.append(
            RawIndicatorCandidate(
                name_raw="血压",
                value_raw=f"{bp.group(1)}/{bp.group(2)}",
                unit_raw=bp.group(3) or "mmHg",
                source="regex",
                confidence=0.9,
                line_context=bp.group(0),
            )
        )
    return out


def rule_structure(artifact: DocumentArtifact) -> tuple[List[RawIndicatorCandidate], PatientMeta | None, list[str]]:
    text, warnings = _first_patient_block(artifact.raw_text)
    patient = _extract_patient(text)
    candidates = _from_tables(artifact)
    regex_hits = _from_regex(text)

    seen = {(c.name_raw, c.value_raw) for c in candidates}
    for c in regex_hits:
        key = (c.name_raw, c.value_raw)
        if key not in seen:
            candidates.append(c)
            seen.add(key)

    return candidates, patient, warnings + artifact.warnings
