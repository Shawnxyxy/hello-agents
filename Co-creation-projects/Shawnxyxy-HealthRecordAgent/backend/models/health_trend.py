"""
健康趋势分析数据模型
支持历史对比和趋势分析的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class TrendDirection(str, Enum):
    """趋势方向"""
    IMPROVING = "improving"      # 改善
    STABLE = "stable"              # 稳定
    WORSENING = "worsening"       # 恶化
    UNKNOWN = "unknown"           # 未知

class IndicatorStatus(str, Enum):
    """指标状态"""
    NORMAL = "normal"
    BORDERLINE = "borderline"
    HIGH = "high"
    LOW = "low"
    ABNORMAL = "abnormal"
    UNKNOWN = "unknown"

@dataclass
class HealthIndicator:
    """健康指标数据点"""
    name: str                      # 指标名称
    value: Any                      # 原始值
    normalized_value: Optional[float] # 标准化数值（用于对比）
    unit: str = ""                 # 单位
    status: IndicatorStatus = IndicatorStatus.UNKNOWN
    risk_level: str = "low"
    analysis: str = ""
    timestamp: str = ""
    canonical_code: Optional[str] = None

    def get_numeric_value(self) -> Optional[float]:
        """尝试获取数值型值"""
        try:
            if isinstance(self.value, (int, float)):
                return float(self.value)
            if isinstance(self.value, str):
                # 尝试从字符串中提取数值
                import re
                numbers = re.findall(r'[-+]?\d*\.?\d+', self.value)
                if numbers:
                    return float(numbers[0])
            return None
        except Exception:
            return None

@dataclass
class HealthReport:
    """健康报告"""
    task_id: str
    user_id: str
    created_at: str
    indicators: List[HealthIndicator]
    overall_risk_level: str = "low"
    risk_factors: List[str] = field(default_factory=list)
    summary: str = ""
    raw_report: Optional[Dict[str, Any]] = None

@dataclass
class IndicatorComparison:
    """单个指标的历史对比"""
    indicator_name: str
    current_value: Any
    previous_value: Any
    change_type: TrendDirection
    change_amount: Optional[float] = None
    change_percentage: Optional[float] = None
    analysis: str = ""
    concern_level: str = "low"  # low, medium, high

@dataclass
class TrendAnalysis:
    """趋势分析结果"""
    user_id: str
    analysis_period: str  # 分析时间段
    indicators_trends: List[Dict[str, Any]]
    overall_trend: TrendDirection
    summary: str
    recommendations: List[str]
    comparison_data: List[IndicatorComparison]

@dataclass
class HealthProgressReport:
    """健康进展报告"""
    user_id: str
    report_period: str
    start_date: str
    end_date: str
    total_reports: int
    improved_indicators: List[str]
    worsened_indicators: List[str]
    stable_indicators: List[str]
    overall_health_score: float
    trend_analysis: TrendAnalysis
    actionable_recommendations: List[str]
