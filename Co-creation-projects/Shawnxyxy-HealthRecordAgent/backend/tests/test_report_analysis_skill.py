"""report_analysis Skill 单元测试（不调用 LLM）。"""

from agents.base import TASKS, complete_task, create_task, update_agent_state
from skills.report_analysis_skill import (
    _read_agent_state,
    build_report_summary,
    extract_report_inner,
)


def test_read_agent_state_string():
    agents = {"PlannerAgent": "running", "ReportAgent": "completed"}
    assert _read_agent_state(agents, "PlannerAgent") == "running"
    assert _read_agent_state(agents, "ReportAgent") == "completed"
    assert _read_agent_state(agents, "Missing") == ""


def test_read_agent_state_dict_legacy():
    agents = {"PlannerAgent": {"status": "running"}}
    assert _read_agent_state(agents, "PlannerAgent") == "running"


def test_extract_report_inner_nested():
    status = {
        "report": {
            "report": {
                "summary": "测试摘要",
                "risk_section": {"overall_risk_level": "medium"},
                "indicator_section": [{"name": "LDL"}],
            }
        }
    }
    inner = extract_report_inner(status)
    assert inner["summary"] == "测试摘要"
    assert inner["risk_section"]["overall_risk_level"] == "medium"


def test_build_report_summary():
    inner = {
        "summary": "总体尚可",
        "risk_section": {"overall_risk_level": "medium"},
        "indicator_section": [{"a": 1}, {"b": 2}],
        "advice_section": ["少盐", "多运动"],
    }
    summary = build_report_summary(inner)
    assert "总体尚可" in summary
    assert "medium" in summary
    assert "2 项" in summary
    assert "2 条" in summary


def test_task_status_integration_keys():
    """模拟 agents.base TASKS 结构，确认 report 键可读。"""
    create_task("t-integration", user_id="u1")
    update_agent_state("t-integration", "PlannerAgent", "completed")
    complete_task(
        "t-integration",
        {
            "report": {
                "summary": "集成测试",
                "risk_section": {"overall_risk_level": "low"},
                "indicator_section": [],
                "advice_section": [],
            }
        },
    )
    status = TASKS["t-integration"]
    inner = extract_report_inner(status)
    assert inner["summary"] == "集成测试"
    assert status["state"] == "completed"
    TASKS.pop("t-integration", None)
