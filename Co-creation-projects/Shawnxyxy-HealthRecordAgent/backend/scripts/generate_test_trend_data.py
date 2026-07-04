"""
生成模拟健康趋势测试数据
用于测试历史对比和趋势分析功能
"""

import sys
import os
from datetime import datetime, timedelta
import json

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import save_completed_report_run, ensure_user
from models.health_trend import IndicatorStatus

# 模拟用户数据
TEST_USER_ID = "test_trend_user_001"

def generate_test_report_data(months_ago: int, scenario: str = "gradual_improvement") -> dict:
    """
    生成测试报告数据

    Args:
        months_ago: 几个月前的数据
        scenario: 场景类型 (gradual_improvement, gradual_worsening, fluctuation)
    """
    # 基础日期计算
    report_date = datetime.now() - timedelta(days=30 * months_ago)

    # 根据不同场景生成不同的数据模式
    if scenario == "gradual_improvement":
        # 逐渐改善的场景
        improvement_factor = months_ago  # 月份越多，基础值越差
        data = {
            "blood_pressure": {
                "systolic": 145 - months_ago * 3,  # 从145逐渐降到130
                "diastolic": 95 - months_ago * 2,     # 从95逐渐降到85
            },
            "blood_sugar": {
                "fasting": 6.5 - months_ago * 0.1,   # 从6.5逐渐降到5.8
            },
            "cholesterol": {
                "total": 6.5 - months_ago * 0.2,     # 从6.5逐渐降到5.5
                "triglyceride": 2.5 - months_ago * 0.15, # 从2.5逐渐降到1.5
            },
            "bmi": 27.3 - months_ago * 0.15,           # 从27.3逐渐降到25.5
        }
        risk_level = "high" if months_ago > 3 else ("medium" if months_ago > 1 else "low")

    elif scenario == "gradual_worsening":
        # 逐渐恶化的场景
        worsening_factor = months_ago
        data = {
            "blood_pressure": {
                "systolic": 125 + months_ago * 2,      # 从125逐渐升到135
                "diastolic": 82 + months_ago * 1,       # 从82逐渐升到87
            },
            "blood_sugar": {
                "fasting": 5.8 + months_ago * 0.1,    # 从5.8逐渐升到6.3
            },
            "cholesterol": {
                "total": 5.2 + months_ago * 0.2,      # 从5.2逐渐升到5.8
                "triglyceride": 1.5 + months_ago * 0.1, # 从1.5逐渐升到2.0
            },
            "bmi": 24.5 + months_ago * 0.2,            # 从24.5逐渐升到25.5
        }
        risk_level = "low" if months_ago > 3 else ("medium" if months_ago > 1 else "high")

    else:  # fluctuation - 波动场景
        # 波动场景
        import random
        random.seed(months_ago * 100)  # 固定随机种子

        data = {
            "blood_pressure": {
                "systolic": 130 + random.randint(-10, 10),
                "diastolic": 85 + random.randint(-5, 5),
            },
            "blood_sugar": {
                "fasting": 6.0 + random.uniform(-0.5, 0.5),
            },
            "cholesterol": {
                "total": 5.8 + random.uniform(-0.5, 0.5),
                "triglyceride": 1.8 + random.uniform(-0.3, 0.3),
            },
            "bmi": 25.8 + random.uniform(-0.5, 0.5),
        }
        risk_level = "medium"

    # 构建报告JSON结构
    report_json = {
        "summary": f"体检报告摘要 - {report_date.strftime('%Y年%m月')}。总体风险等级：{risk_level}。",
        "report": {
            "summary": f"本次体检显示{'部分指标异常' if risk_level != 'low' else '各项指标基本正常'}。",
            "detailed_findings": [],
            "recommendations": []
        },
        "indicators": [],
        "risk_assessment": {
            "overall_risk_level": risk_level,
            "risk_factors": [],
            "potential_conditions": [],
            "confidence": 0.85
        }
    }

    # 添加指标数据
    indicators = [
        {
            "name": "血压",
            "value": f"{data['blood_pressure']['systolic']}/{data['blood_pressure']['diastolic']} mmHg",
            "normalized_value": data['blood_pressure']['systolic'],
            "unit": "mmHg",
            "status": _get_status(data['blood_pressure']['systolic'], (90, 120), (120, 140)),
            "risk_level": "high" if data['blood_pressure']['systolic'] > 140 else "medium" if data['blood_pressure']['systolic'] > 120 else "low",
            "analysis": _get_blood_pressure_analysis(data['blood_pressure'])
        },
        {
            "name": "空腹血糖",
            "value": f"{data['blood_sugar']['fasting']:.1f} mmol/L",
            "normalized_value": data['blood_sugar']['fasting'],
            "unit": "mmol/L",
            "status": _get_status(data['blood_sugar']['fasting'], (3.9, 6.1), (6.1, 7.0)),
            "risk_level": "high" if data['blood_sugar']['fasting'] > 7.0 else "medium" if data['blood_sugar']['fasting'] > 6.1 else "low",
            "analysis": _get_blood_sugar_analysis(data['blood_sugar']['fasting'])
        },
        {
            "name": "总胆固醇",
            "value": f"{data['cholesterol']['total']:.1f} mmol/L",
            "normalized_value": data['cholesterol']['total'],
            "unit": "mmol/L",
            "status": _get_status(data['cholesterol']['total'], (0, 5.2), (5.2, 6.2)),
            "risk_level": "high" if data['cholesterol']['total'] > 6.2 else "medium" if data['cholesterol']['total'] > 5.2 else "low",
            "analysis": _get_cholesterol_analysis(data['cholesterol']['total'])
        },
        {
            "name": "甘油三酯",
            "value": f"{data['cholesterol']['triglyceride']:.1f} mmol/L",
            "normalized_value": data['cholesterol']['triglyceride'],
            "unit": "mmol/L",
            "status": _get_status(data['cholesterol']['triglyceride'], (0, 1.7), (1.7, 2.3)),
            "risk_level": "high" if data['cholesterol']['triglyceride'] > 2.3 else "medium" if data['cholesterol']['triglyceride'] > 1.7 else "low",
            "analysis": _get_triglyceride_analysis(data['cholesterol']['triglyceride'])
        },
        {
            "name": "BMI",
            "value": f"{data['bmi']:.1f}",
            "normalized_value": data['bmi'],
            "unit": "",
            "status": _get_status(data['bmi'], (18.5, 24.0), (24.0, 28.0)),
            "risk_level": "high" if data['bmi'] > 28.0 else "medium" if data['bmi'] > 24.0 else "low",
            "analysis": _get_bmi_analysis(data['bmi'])
        }
    ]

    report_json["indicators"] = indicators

    # 添加风险因素
    if risk_level != "low":
        report_json["risk_assessment"]["risk_factors"] = _extract_risk_factors(indicators)

    return report_json

def _get_status(value: float, ideal_range: tuple, warning_range: tuple) -> str:
    """根据数值范围判断状态"""
    if ideal_range[0] <= value <= ideal_range[1]:
        return "normal"
    elif warning_range[0] <= value <= warning_range[1]:
        return "borderline"
    elif value < ideal_range[0] or value > warning_range[1]:
        return "abnormal"
    else:
        return "high"

def _get_blood_pressure_analysis(bp_data: dict) -> str:
    systolic = bp_data['systolic']
    diastolic = bp_data['diastolic']

    if systolic > 140 or diastolic > 90:
        return f"血压偏高（{systolic}/{diastolic} mmHg），建议控制钠盐摄入，增加有氧运动"
    elif systolic > 120 or diastolic > 80:
        return f"血压处于正常高值（{systolic}/{diastolic} mmHg），注意生活方式管理"
    else:
        return f"血压正常（{systolic}/{diastolic} mmHg），继续保持"

def _get_blood_sugar_analysis(sugar: float) -> str:
    if sugar > 7.0:
        return f"空腹血糖偏高（{sugar:.1f} mmol/L），建议控制糖分摄入，考虑减重"
    elif sugar > 6.1:
        return f"空腹血糖处于正常高值（{sugar:.1f} mmol/L），注意饮食控制"
    else:
        return f"空腹血糖正常（{sugar:.1f} mmol/L），继续保持"

def _get_cholesterol_analysis(cholesterol: float) -> str:
    if cholesterol > 6.2:
        return f"总胆固醇偏高（{cholesterol:.1f} mmol/L），建议减少高脂肪食物摄入"
    elif cholesterol > 5.2:
        return f"总胆固醇处于正常高值（{cholesterol:.1f} mmol/L），注意饮食结构"
    else:
        return f"总胆固醇正常（{cholesterol:.1f} mmol/L），继续保持"

def _get_triglyceride_analysis(triglyceride: float) -> str:
    if triglyceride > 2.3:
        return f"甘油三酯偏高（{triglyceride:.1f} mmol/L），建议减少糖分和精细碳水化合物"
    elif triglyceride > 1.7:
        return f"甘油三酯处于正常高值（{triglyceride:.1f} mmol/L），注意饮食控制"
    else:
        return f"甘油三酯正常（{triglyceride:.1f} mmol/L），继续保持"

def _get_bmi_analysis(bmi: float) -> str:
    if bmi > 28.0:
        return f"BMI偏高（{bmi:.1f}），属于肥胖范围，建议减重"
    elif bmi > 24.0:
        return f"BMI处于正常高值（{bmi:.1f}），属于超重范围，注意体重管理"
    elif bmi < 18.5:
        return f"BMI偏低（{bmi:.1f}），注意营养均衡"
    else:
        return f"BMI正常（{bmi:.1f}），继续保持"

def _extract_risk_factors(indicators: list) -> list:
    """从指标中提取风险因素"""
    factors = []
    for indicator in indicators:
        if indicator['risk_level'] in ['medium', 'high']:
            factors.append(indicator['name'])
    return factors[:5]  # 最多返回5个

def create_mock_report(task_id: str, months_ago: int, scenario: str = "gradual_improvement"):
    """创建模拟报告"""
    report_json = generate_test_report_data(months_ago, scenario)

    # 模拟创建时间
    created_at = (datetime.now() - timedelta(days=30 * months_ago)).isoformat()

    # 模拟摘要文本
    summary_text = f"体检报告 - {created_at.split('T')[0]}。主要指标：血压、血糖、血脂、BMI等。"

    return {
        "task_id": task_id,
        "report_json": report_json,
        "summary_text": summary_text,
        "created_at": created_at
    }

def main():
    """主函数：生成测试数据"""
    print(f"正在为用户 {TEST_USER_ID} 生成模拟健康趋势数据...")

    # 确保用户存在
    ensure_user(TEST_USER_ID)

    # 生成多个时间点的数据（最近6个月，每月一次体检）
    scenarios = {
        5: "gradual_improvement",  # 5个月前 - 数据较差
        4: "gradual_improvement",  # 4个月前 - 稍有改善
        3: "gradual_improvement",  # 3个月前 - 继续改善
        2: "fluctuation",          # 2个月前 - 有波动
        1: "gradual_improvement",  # 1个月前 - 基本稳定
        0: "gradual_improvement"   # 现在 - 数据良好
    }

    created_reports = []

    for months_ago, scenario in scenarios.items():
        task_id = f"mock_task_{TEST_USER_ID}_{months_ago}months_ago"

        mock_data = create_mock_report(task_id, months_ago, scenario)

        # 保存到数据库
        save_completed_report_run(
            user_id=TEST_USER_ID,
            task_id=task_id,
            final_report=mock_data["report_json"],
            agent_trace={}
        )

        created_reports.append({
            "task_id": task_id,
            "months_ago": months_ago,
            "created_at": mock_data["created_at"],
            "scenario": scenario
        })

        print(f"✓ 创建报告: {task_id} ({months_ago}个月前)")

    print(f"\n总共创建了 {len(created_reports)} 份模拟体检报告")
    print(f"用户ID: {TEST_USER_ID}")
    print(f"时间范围: 5个月前至今")
    print(f"数据场景: 逐渐改善为主，中间有波动")

    # 输出详细数据概览
    print("\n" + "="*60)
    print("详细数据概览:")
    print("="*60)

    for report in created_reports:
        print(f"\n[{report['months_ago']}个月前 - {report['created_at'].split('T')[0]}]")
        print(f"任务ID: {report['task_id']}")
        print(f"场景: {report['scenario']}")

        # 读取刚才保存的数据以显示详情
        from memory.store import get_report_run
        saved_report = get_report_run(report['task_id'])
        if saved_report:
            try:
                report_data = json.loads(saved_report['report_json'])
                indicators = report_data.get('indicators', [])
                risk_assessment = report_data.get('risk_assessment', {})

                print(f"风险等级: {risk_assessment.get('overall_risk_level', 'unknown')}")

                for ind in indicators:
                    print(f"  {ind['name']}: {ind['value']} ({ind['status']})")

            except Exception as e:
                print(f"  (无法解析报告数据: {e})")

    print("\n" + "="*60)
    print("测试数据生成完成！")
    print("可以使用以下API进行测试:")
    print(f"1. GET /api/health/users/{TEST_USER_ID}/report_history")
    print(f"2. GET /api/health/users/{TEST_USER_ID}/trend_analysis")
    print(f"3. GET /api/health/users/{TEST_USER_ID}/comparison")
    print("="*60)

if __name__ == "__main__":
    main()
