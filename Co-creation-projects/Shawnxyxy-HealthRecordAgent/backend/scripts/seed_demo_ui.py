"""
写入演示用户 demo-ui-user 的饮食 run + 反馈，供前端「历史记录」Tab 联调。
用法：cd backend && .venv/bin/python scripts/seed_demo_ui.py
"""

from __future__ import annotations

import os
import sys
import uuid

# 保证从 backend 目录运行时能 import memory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import insert_diet_reflect, save_diet_run  # noqa: E402


DEMO_USER = "demo-ui-user"


def main() -> None:
    run_id = str(uuid.uuid4())
    save_diet_run(
        user_id=DEMO_USER,
        run_id=run_id,
        input_payload={
            "context": {
                "goal": "muscle_gain",
                "today_food_log_text": "早餐豆浆300ml+鸡蛋2个；午餐鸡腿饭；晚餐前香蕉1根",
                "activity_context": "今晚力量训练60分钟",
                "free_notes": "演示数据：训练后便利店补蛋白",
            }
        },
        steps_trace=[
            {"phase": "nutritionist", "attempts": [{"ok": True}]},
            {"phase": "coach", "attempts": [{"ok": True}]},
            {"phase": "habit", "attempts": [{"ok": True}]},
        ],
        output_payload={
            "run_id": run_id,
            "user_id": DEMO_USER,
            "schema_version": "1",
            "pipeline_mode": "multi_agent",
            "meal_plan": {
                "total_est_protein_g": 92,
                "items": [
                    {
                        "name": "希腊酸奶",
                        "portion": "约 150g",
                        "est_protein_g": 15,
                        "why": "便利店常见，蛋白密度高",
                    },
                    {
                        "name": "水煮蛋",
                        "portion": "2 个",
                        "est_protein_g": 12,
                        "why": "易购买、蛋白稳定",
                    },
                ],
                "tips": "演示数据：可与豆浆搭配补充水分。",
            },
            "planning": {"reasoning": "演示：估算缺口并优先便利店可得蛋白来源。"},
        },
    )
    rid = insert_diet_reflect(
        user_id=DEMO_USER,
        diet_run_id=run_id,
        followed=False,
        reason_code="cant_buy",
        reason_detail="演示：目标款酸奶缺货",
    )
    print(f"OK user={DEMO_USER} run_id={run_id} reflect_id={rid}")


if __name__ == "__main__":
    main()
