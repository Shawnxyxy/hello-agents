"""报告解析流水线测试（无 LLM）。"""

from pathlib import Path

import pytest

from service.report_parsing import ReportParsingPipeline

_SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_reports" / "report.txt"


def test_parse_sample_report_txt():
    text = _SAMPLE.read_text(encoding="utf-8")
    parsed = ReportParsingPipeline().ingest_text(text, "report.txt")

    assert parsed.quality.indicator_count >= 5
    codes = {i.canonical_code for i in parsed.indicators}
    assert "total_cholesterol" in codes or "ldl_c" in codes
    assert parsed.quality.overall_score > 0.4
    assert parsed.artifact.raw_text


def test_parse_blood_pressure_split():
    text = """
姓名：测试
性别：男
年龄：30岁
血压：138/88 mmHg
总胆固醇：6.0 mmol/L
空腹血糖：5.6 mmol/L
"""
    parsed = ReportParsingPipeline().ingest_text(text)
    codes = {i.canonical_code for i in parsed.indicators}
    assert "sbp" in codes
    assert "dbp" in codes


def test_multi_patient_warning():
    text = _SAMPLE.read_text(encoding="utf-8")
    parsed = ReportParsingPipeline().ingest_text(text)
    assert any("多份报告" in w for w in parsed.quality.warnings)


def test_catalog_match_ldl_aliases():
    from service.report_parsing.normalizer.catalog import match_canonical

    assert match_canonical("LDL-C")[0] == "ldl_c"
    assert match_canonical("低密度脂蛋白")[0] == "ldl_c"


def test_golden_single_patient_fixture():
    import yaml

    fixture = (
        Path(__file__).resolve().parent / "fixtures" / "reports" / "sample_single_patient.txt"
    )
    meta_path = fixture.parent / "expected" / "sample_single_patient.meta.yaml"
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    parsed = ReportParsingPipeline().ingest_text(fixture.read_text(encoding="utf-8"))

    codes = {i.canonical_code for i in parsed.indicators}
    for code in meta["expected_canonical_codes"]:
        assert code in codes, f"missing {code}, got {codes}"
    assert parsed.quality.indicator_count >= meta["min_indicator_count"]


def test_ocr_unavailable_when_disabled():
    from core.config import get_config
    from service.report_parsing.errors import ParseError, ParseErrorCode
    from service.report_parsing.router import _try_ocr_fallback

    orig = get_config().parse.ocr_enabled
    try:
        get_config().parse.ocr_enabled = False
        with pytest.raises(ParseError) as exc:
            _try_ocr_fallback(b"%PDF-1.4", "scan.pdf")
        assert exc.value.code == ParseErrorCode.OCR_UNAVAILABLE
    finally:
        get_config().parse.ocr_enabled = orig


def test_pdf_magic_bytes_overrides_txt_extension():
    from service.report_parsing.router import detect_format

    assert detect_format(b"%PDF-1.4 content", "report.txt") == "pdf"


def test_quality_score_reflects_text_coverage():
    from service.report_parsing.quality import compute_parse_quality
    from service.report_parsing.schemas import NormalizedIndicator

    ind = NormalizedIndicator(
        canonical_code="bmi", display_name="BMI", value=22.0, confidence=0.9
    )
    high = compute_parse_quality([ind], [], text_coverage=1.0, extraction_method="test")
    low = compute_parse_quality([ind], [], text_coverage=0.2, extraction_method="test")
    assert low.overall_score < high.overall_score
    assert low.text_coverage == 0.2


def test_catalog_no_substring_false_positive():
    from service.report_parsing.normalizer.catalog import match_canonical

    assert match_canonical("餐后2小时血糖") is None
    assert match_canonical("空腹血糖")[0] == "fasting_glucose"


def test_trend_extract_indicators_from_nested_section():
    from service.trend_analysis import TrendAnalysisService

    svc = TrendAnalysisService()
    raw = {
        "report": {
            "indicator_section": {
                "indicators": [
                    {"name": "LDL", "canonical_code": "ldl_c", "value": 4.5, "normalized_value": 4.5}
                ]
            }
        }
    }
    inner = raw["report"]
    items = svc._extract_indicators_from_json(raw, inner, "2026-01-01")
    assert len(items) == 1
    assert items[0].canonical_code == "ldl_c"


def test_indicator_list_from_agent_result():
    from service.health_analysis import _indicator_list_from_agent_result

    wrapped = {"indicators": [{"name": "LDL", "value": 4.5}]}
    assert len(_indicator_list_from_agent_result(wrapped)) == 1
    assert _indicator_list_from_agent_result([]) == []


def test_parse_api_text():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    sample = (
        Path(__file__).resolve().parent / "fixtures" / "reports" / "sample_single_patient.txt"
    ).read_text(encoding="utf-8")
    res = client.post("/api/health/parse", json={"report_text": sample})
    assert res.status_code == 200
    body = res.json()
    assert body["quality"]["indicator_count"] >= 6
    assert body["schema_version"] == "1.0"

