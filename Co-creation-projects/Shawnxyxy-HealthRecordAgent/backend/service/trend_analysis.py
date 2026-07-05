"""
健康趋势分析服务
实现历史对比、趋势分析和健康进展追踪
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from models.health_trend import (
    HealthIndicator, HealthReport, IndicatorComparison,
    TrendAnalysis, TrendDirection, IndicatorStatus,
    HealthProgressReport
)
from memory.store import list_report_runs_for_user, get_report_run

logger = logging.getLogger(__name__)

class TrendAnalysisService:
    """趋势分析服务"""

    # 指标类型定义
    INDICATOR_CATEGORIES = {
        "血压": {
            "type": "blood_pressure",
            "unit": "mmHg",
            "ideal_range": (90, 120),  # 收缩压正常范围
            "warning_range": (120, 140),
            "danger_range": (140, 180)
        },
        "血糖": {
            "type": "blood_sugar",
            "unit": "mmol/L",
            "ideal_range": (3.9, 6.1),
            "warning_range": (6.1, 7.0),
            "danger_range": (7.0, 11.1)
        },
        "总胆固醇": {
            "type": "cholesterol_total",
            "unit": "mmol/L",
            "ideal_range": (0, 5.2),
            "warning_range": (5.2, 6.2),
            "danger_range": (6.2, 10.0)
        },
        "甘油三酯": {
            "type": "triglyceride",
            "unit": "mmol/L",
            "ideal_range": (0, 1.7),
            "warning_range": (1.7, 2.3),
            "danger_range": (2.3, 5.0)
        },
        "BMI": {
            "type": "bmi",
            "unit": "",
            "ideal_range": (18.5, 24.0),
            "warning_range": (24.0, 28.0),
            "danger_range": (28.0, 35.0)
        },
        "心率": {
            "type": "heart_rate",
            "unit": "bpm",
            "ideal_range": (60, 100),
            "warning_range": (100, 110),
            "danger_range": (110, 140)
        }
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _parse_created_at(value: str) -> Optional[datetime]:
        """安全解析 ISO 时间戳，失败返回 None。"""
        if not value:
            return None
        try:
            raw = value.strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None

    def get_user_reports(self, user_id: str, limit: int = 10) -> List[HealthReport]:
        """获取用户的历史报告（加载完整 report_json）。"""
        report_data = list_report_runs_for_user(user_id, limit)
        reports = []

        for row in report_data:
            try:
                task_id = row.get("task_id", "")
                full = get_report_run(task_id) if task_id else None
                if full:
                    report = self._parse_full_report(full)
                else:
                    report = self._parse_report_row(row)
                if report:
                    reports.append(report)
            except Exception as e:
                self.logger.warning(f"解析报告失败: {e}")
                continue

        reports.sort(key=lambda x: x.created_at, reverse=True)
        return reports

    def _parse_full_report(self, full: Dict[str, Any]) -> Optional[HealthReport]:
        """从 get_report_run() 结果解析 HealthReport。"""
        task_id = full.get("task_id", "")
        user_id = full.get("user_id", "")
        created_at = full.get("created_at", "")
        raw = full.get("report") or {}
        if isinstance(raw, dict) and "report" in raw:
            inner = raw["report"]
        else:
            inner = raw if isinstance(raw, dict) else {}

        indicators = self._extract_indicators_from_json(raw, inner, created_at)
        risk_data = inner.get("risk_section") or raw.get("risk_assessment") or {}
        summary = inner.get("summary") or full.get("summary_text") or ""

        return HealthReport(
            task_id=task_id,
            user_id=user_id,
            created_at=created_at,
            indicators=indicators,
            overall_risk_level=str(risk_data.get("overall_risk_level", "low")),
            risk_factors=list(risk_data.get("risk_factors") or []),
            summary=str(summary),
            raw_report=raw,
        )

    def _extract_indicators_from_json(
        self, raw: Dict[str, Any], inner: Dict[str, Any], created_at: str
    ) -> List[HealthIndicator]:
        indicators: List[HealthIndicator] = []
        candidates = (
            raw.get("indicators")
            or inner.get("indicator_section")
            or (raw.get("indicator_results") or {}).get("indicators")
            or (inner.get("indicator_results") or {}).get("indicators")
        )
        if isinstance(candidates, dict) and isinstance(candidates.get("indicators"), list):
            candidates = candidates["indicators"]
        if not isinstance(candidates, list):
            return indicators
        for ind in candidates:
            if not isinstance(ind, dict):
                continue
            status_raw = ind.get("status", "unknown")
            try:
                status = IndicatorStatus(status_raw)
            except ValueError:
                status = IndicatorStatus.BORDERLINE
            indicators.append(
                HealthIndicator(
                    name=ind.get("name", ind.get("indicator_name", ind.get("display_name", "未知指标"))),
                    value=ind.get("value", ind.get("result")),
                    normalized_value=ind.get("normalized_value"),
                    unit=ind.get("unit", ""),
                    status=status,
                    risk_level=ind.get("risk_level", "low"),
                    analysis=str(ind.get("analysis", "")),
                    timestamp=created_at,
                    canonical_code=ind.get("canonical_code"),
                )
            )
        return indicators

    def _parse_report_row(self, row: Dict[str, Any]) -> Optional[HealthReport]:
        """解析 list_report_runs 摘要行（无完整 JSON 时降级）。"""
        try:
            task_id = row.get("task_id", "")
            user_id = row.get("user_id", "")
            created_at = row.get("created_at", "")
            summary = row.get("summary_text") or ""
            if not summary:
                return None
            return HealthReport(
                task_id=task_id,
                user_id=user_id,
                created_at=created_at,
                indicators=[],
                overall_risk_level="unknown",
                risk_factors=[],
                summary=summary,
                raw_report={},
            )
        except Exception as e:
            self.logger.error(f"解析报告异常: {e}", exc_info=True)
            return None

    def compare_with_previous(self, user_id: str) -> List[IndicatorComparison]:
        """与上一次体检报告对比"""
        reports = self.get_user_reports(user_id, limit=2)

        if len(reports) < 2:
            return []

        current_report = reports[0]
        previous_report = reports[1]

        comparisons = []

        # 对比相同名称的指标
        for current_indicator in current_report.indicators:
            previous_indicator = self._find_matching_indicator(
                previous_report.indicators, current_indicator
            )

            if previous_indicator:
                comparison = self._compare_indicators(current_indicator, previous_indicator)
                if comparison:
                    comparisons.append(comparison)

        return comparisons

    def _find_indicator_by_name(self, indicators: List[HealthIndicator], name: str) -> Optional[HealthIndicator]:
        """按 canonical_code 或名称查找指标。"""
        for ind in indicators:
            if ind.canonical_code and name and ind.canonical_code == name:
                return ind
        for ind in indicators:
            if name in ind.name or ind.name in name:
                return ind
        return None

    def _find_matching_indicator(
        self, indicators: List[HealthIndicator], current: HealthIndicator
    ) -> Optional[HealthIndicator]:
        if current.canonical_code:
            for ind in indicators:
                if ind.canonical_code == current.canonical_code:
                    return ind
        return self._find_indicator_by_name(indicators, current.name)

    def _compare_indicators(self, current: HealthIndicator, previous: HealthIndicator) -> Optional[IndicatorComparison]:
        """对比两个指标"""
        try:
            current_numeric = current.get_numeric_value()
            previous_numeric = previous.get_numeric_value()

            if current_numeric is None or previous_numeric is None:
                return None

            change_amount = current_numeric - previous_numeric

            # 计算变化百分比
            if previous_numeric != 0:
                change_percentage = (change_amount / abs(previous_numeric)) * 100
            else:
                change_percentage = 0

            # 判断变化方向和意义
            change_type, analysis, concern_level = self._analyze_indicator_change(
                current.name, change_amount, current.status, previous.status
            )

            return IndicatorComparison(
                indicator_name=current.name,
                current_value=current.value,
                previous_value=previous.value,
                change_type=change_type,
                change_amount=change_amount,
                change_percentage=change_percentage,
                analysis=analysis,
                concern_level=concern_level
            )

        except Exception as e:
            self.logger.warning(f"指标对比失败: {e}")
            return None

    def _analyze_indicator_change(self, indicator_name: str, change_amount: float,
                               current_status: IndicatorStatus, previous_status: IndicatorStatus) -> tuple:
        """分析指标变化的意义"""
        concern_level = "low"
        change_type = TrendDirection.STABLE
        analysis = ""

        # 根据指标类型判断变化是好是坏
        category = self._get_indicator_category(indicator_name)

        if category:
            # 对于需要降低的指标（血压、血糖、胆固醇等）
            if category["type"] in ["blood_pressure", "blood_sugar", "cholesterol_total", "triglyceride", "bmi"]:
                if abs(change_amount) < category.get("change_threshold", 0.5):
                    change_type = TrendDirection.STABLE
                    analysis = f"{indicator_name}保持稳定，变化{change_amount:+.2f}{category.get('unit', '')}"
                elif change_amount < 0:
                    change_type = TrendDirection.IMPROVING
                    analysis = f"{indicator_name}有所改善，降低{abs(change_amount):.2f}{category.get('unit', '')}"
                    if previous_status in [IndicatorStatus.HIGH, IndicatorStatus.ABNORMAL]:
                        concern_level = "high"  # 好的变化需要关注
                else:
                    change_type = TrendDirection.WORSENING
                    analysis = f"{indicator_name}有所上升，增加{change_amount:.2f}{category.get('unit', '')}"
                    if current_status in [IndicatorStatus.HIGH, IndicatorStatus.ABNORMAL]:
                        concern_level = "high"

            # 对于心率等指标
            elif category["type"] == "heart_rate":
                if abs(change_amount) < 5:
                    change_type = TrendDirection.STABLE
                    analysis = f"{indicator_name}变化不大"
                elif abs(change_amount) < 15:
                    change_type = TrendDirection.STABLE
                    analysis = f"{indicator_name}在正常波动范围内"
                else:
                    # 心率变化可能受多种因素影响，需要结合其他指标
                    change_type = TrendDirection.UNKNOWN
                    analysis = f"{indicator_name}变化较大，建议结合其他指标综合分析"
        else:
            # 未知指标类型
            if abs(change_amount) < 1.0:
                change_type = TrendDirection.STABLE
                analysis = f"{indicator_name}变化较小"
            else:
                change_type = TrendDirection.UNKNOWN
                analysis = f"{indicator_name}有明显变化，需要结合专业判断"

        return change_type, analysis, concern_level

    def _get_indicator_category(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """获取指标分类信息"""
        for category_name, category_info in self.INDICATOR_CATEGORIES.items():
            if category_name in indicator_name or indicator_name in category_name:
                return category_info
        return None

    def analyze_trends(self, user_id: str, period_days: int = 90) -> TrendAnalysis:
        """分析用户的健康趋势"""
        reports = self.get_user_reports(user_id, limit=20)

        if len(reports) < 2:
            return self._create_insufficient_data_trend(user_id, period_days)

        # 筛选指定时间段内的报告
        cutoff_date = datetime.now() - timedelta(days=period_days)
        filtered_reports = [
            r for r in reports
            if (dt := self._parse_created_at(r.created_at)) and dt >= cutoff_date
        ]

        if len(filtered_reports) < 2:
            return self._create_insufficient_data_trend(user_id, period_days)

        # 分析各指标的趋势
        indicators_trends = []
        all_comparisons = []

        # 对比相邻的报告
        for i in range(len(filtered_reports) - 1):
            current = filtered_reports[i]
            previous = filtered_reports[i + 1]

            for current_indicator in current.indicators:
                previous_indicator = self._find_indicator_by_name(previous.indicators, current_indicator.name)
                if previous_indicator:
                    comparison = self._compare_indicators(current_indicator, previous_indicator)
                    if comparison:
                        all_comparisons.append(comparison)

        # 汇总指标趋势
        indicator_trend_dict = defaultdict(list)
        for comparison in all_comparisons:
            indicator_trend_dict[comparison.indicator_name].append(comparison)

        for indicator_name, comparisons in indicator_trend_dict.items():
            trend_summary = self._summarize_indicator_trend(indicator_name, comparisons)
            indicators_trends.append(trend_summary)

        # 判断整体趋势
        overall_trend = self._determine_overall_trend(indicators_trends)

        # 生成总结和建议
        summary = self._generate_trend_summary(indicators_trends, overall_trend, len(filtered_reports))
        recommendations = self._generate_trend_recommendations(indicators_trends, overall_trend)

        # 获取最新的对比数据
        latest_comparison = self.compare_with_previous(user_id)

        return TrendAnalysis(
            user_id=user_id,
            analysis_period=f"{period_days}天",
            indicators_trends=indicators_trends,
            overall_trend=overall_trend,
            summary=summary,
            recommendations=recommendations,
            comparison_data=latest_comparison
        )

    def _summarize_indicator_trend(self, indicator_name: str, comparisons: List[IndicatorComparison]) -> Dict[str, Any]:
        """汇总单个指标的趋势"""
        improving_count = sum(1 for c in comparisons if c.change_type == TrendDirection.IMPROVING)
        worsening_count = sum(1 for c in comparisons if c.change_type == TrendDirection.WORSENING)
        stable_count = sum(1 for c in comparisons if c.change_type == TrendDirection.STABLE)

        # 计算平均变化
        total_change = sum(c.change_amount or 0 for c in comparisons if c.change_amount is not None)
        avg_change = total_change / len(comparisons) if comparisons else 0

        # 判断总体趋势
        if worsening_count > improving_count:
            trend = TrendDirection.WORSENING
        elif improving_count > worsening_count:
            trend = TrendDirection.IMPROVING
        else:
            trend = TrendDirection.STABLE

        return {
            "indicator_name": indicator_name,
            "trend": trend.value,
            "comparisons_count": len(comparisons),
            "improving_count": improving_count,
            "worsening_count": worsening_count,
            "stable_count": stable_count,
            "average_change": round(avg_change, 2),
            "latest_value": comparisons[0].current_value if comparisons else None,
            "earliest_value": comparisons[-1].previous_value if comparisons else None
        }

    def _determine_overall_trend(self, indicators_trends: List[Dict[str, Any]]) -> TrendDirection:
        """判断整体健康趋势"""
        if not indicators_trends:
            return TrendDirection.UNKNOWN

        improving_count = sum(1 for t in indicators_trends if t["trend"] == TrendDirection.IMPROVING.value)
        worsening_count = sum(1 for t in indicators_trends if t["trend"] == TrendDirection.WORSENING.value)

        if worsening_count > improving_count * 1.5:  # 恶化明显多于改善
            return TrendDirection.WORSENING
        elif improving_count > worsening_count * 1.5:  # 改善明显多于恶化
            return TrendDirection.IMPROVING
        else:
            return TrendDirection.STABLE

    def _generate_trend_summary(self, indicators_trends: List[Dict[str, Any]],
                               overall_trend: TrendDirection, report_count: int) -> str:
        """生成趋势分析总结"""
        if overall_trend == TrendDirection.IMPROVING:
            base_summary = f"在最近的{report_count}次体检中，您的整体健康状况呈改善趋势。"
        elif overall_trend == TrendDirection.WORSENING:
            base_summary = f"在最近的{report_count}次体检中，您的整体健康状况有所下滑，需要引起重视。"
        else:
            base_summary = f"在最近的{report_count}次体检中，您的整体健康状况保持相对稳定。"

        # 提取重点变化
        important_changes = []
        for trend in indicators_trends:
            if trend["trend"] in [TrendDirection.IMPROVING.value, TrendDirection.WORSENING.value]:
                direction = "改善" if trend["trend"] == TrendDirection.IMPROVING.value else "恶化"
                important_changes.append(f"{trend['indicator_name']}{direction}")

        if important_changes:
            base_summary += f" 主要变化包括：{', '.join(important_changes)}。"

        return base_summary

    def _generate_trend_recommendations(self, indicators_trends: List[Dict[str, Any]],
                                     overall_trend: TrendDirection) -> List[str]:
        """生成基于趋势的建议"""
        recommendations = []

        # 基于整体趋势的建议
        if overall_trend == TrendDirection.WORSENING:
            recommendations.append("建议尽快咨询专业医生，制定针对性的健康管理计划")
            recommendations.append("重点关注持续恶化的指标，必要时进行专项检查")
        elif overall_trend == TrendDirection.STABLE:
            recommendations.append("您的健康状况相对稳定，继续保持当前的饮食和生活习惯")
            recommendations.append("建议定期体检，及时发现潜在的健康风险")

        # 基于具体指标的建议
        for trend in indicators_trends:
            if trend["trend"] == TrendDirection.WORSENING.value:
                recommendations.append(f"注意{trend['indicator_name']}的持续恶化，建议调整相关的生活方式")
            elif trend["trend"] == TrendDirection.IMPROVING.value:
                recommendations.append(f"继续保持有利于{trend['indicator_name']}改善的当前做法")

        return list(set(recommendations))[:5]  # 去重并限制数量

    def _create_insufficient_data_trend(self, user_id: str, period_days: int) -> TrendAnalysis:
        """数据不足时的趋势分析"""
        return TrendAnalysis(
            user_id=user_id,
            analysis_period=f"{period_days}天",
            indicators_trends=[],
            overall_trend=TrendDirection.UNKNOWN,
            summary="数据不足，无法进行趋势分析。建议至少进行2次体检后再查看趋势变化。",
            recommendations=["定期进行健康体检，积累数据以便分析健康趋势"],
            comparison_data=[]
        )

    def generate_progress_report(
        self,
        user_id: str,
        trend: Optional[TrendAnalysis] = None,
    ) -> Optional[HealthProgressReport]:
        """生成健康进展报告；可传入已计算的 trend 避免重复分析。"""
        reports = self.get_user_reports(user_id, limit=20)

        if len(reports) < 2:
            return None

        start_date = self._parse_created_at(reports[-1].created_at)
        end_date = self._parse_created_at(reports[0].created_at)
        if not start_date or not end_date:
            self.logger.warning("报告 created_at 无法解析，跳过进展报告")
            return None

        report_period = f"{(end_date - start_date).days}天"
        trend_analysis = trend or self.analyze_trends(user_id)

        # 汇总指标变化
        improved_indicators = []
        worsened_indicators = []
        stable_indicators = []

        for trend in trend_analysis.indicators_trends:
            if trend["trend"] == TrendDirection.IMPROVING.value:
                improved_indicators.append(trend["indicator_name"])
            elif trend["trend"] == TrendDirection.WORSENING.value:
                worsened_indicators.append(trend["indicator_name"])
            else:
                stable_indicators.append(trend["indicator_name"])

        # 计算整体健康评分（简化版）
        health_score = self._calculate_health_score(reports)

        return HealthProgressReport(
            user_id=user_id,
            report_period=report_period,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_reports=len(reports),
            improved_indicators=improved_indicators,
            worsened_indicators=worsened_indicators,
            stable_indicators=stable_indicators,
            overall_health_score=health_score,
            trend_analysis=trend_analysis,
            actionable_recommendations=trend_analysis.recommendations
        )

    def _calculate_health_score(self, reports: List[HealthReport]) -> float:
        """计算整体健康评分（0-100）"""
        if not reports:
            return 50.0

        latest_report = reports[0]

        # 基于指标状态计算得分
        total_score = 0
        score_count = 0

        for indicator in latest_report.indicators:
            score = 50  # 基础分

            if indicator.status == IndicatorStatus.NORMAL:
                score = 85
            elif indicator.status == IndicatorStatus.BORDERLINE:
                score = 70
            elif indicator.status in [IndicatorStatus.HIGH, IndicatorStatus.LOW]:
                score = 55
            elif indicator.status == IndicatorStatus.ABNORMAL:
                score = 30

            # 考虑风险等级
            if indicator.risk_level == "low":
                score += 10
            elif indicator.risk_level == "medium":
                score -= 5
            elif indicator.risk_level == "high":
                score -= 15

            total_score += max(0, min(100, score))
            score_count += 1

        if score_count == 0:
            return 50.0

        return round(total_score / score_count, 1)