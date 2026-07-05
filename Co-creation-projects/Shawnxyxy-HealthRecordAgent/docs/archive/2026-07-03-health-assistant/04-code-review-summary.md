# Code Review 摘要与修复记录

**归档日期:** 2026-07-04

---

## 审查结论

| 轮次 | 结论 |
|------|------|
| 首轮 CR | Critical #1–#4 必须修复后方可 Demo |
| Important 修复 | #5–#12 体验与稳定性 |
| Phase 4 CR | Important #14–#19 |
| 前端 CR | 发送无反应（user_id 阻塞）+ UI 改版 |

**最终状态:** 可 Demo，可合 PR；pytest 20/20，E2E 验证通过。

---

## Critical 修复（首轮）

| # | 问题 | 修复 |
|---|------|------|
| 1 | `final_report` vs `report` 字段名错误 | report_analysis_skill 改用 `report` |
| 2 | Agent 状态字符串/字典混用 | `_read_agent_state()` 兼容 |
| 3 | 摘要字段名错误 | risk_section / indicator_section 等 |
| 4 | Skill 异常裸 500 | `run_skill_safe` + SSE error 事件 |

---

## Important 修复（第二轮）

| # | 问题 | 修复 |
|---|------|------|
| 5 | 追问无报告上下文 | report_context.py + user_id 校验 |
| 7/8 | 刷新丢失历史 | initChatIfReady + 历史 API |
| 9/10 | PDF 500 / DB 迁移丢数据 | try/except + 非破坏性迁移 |
| 11 | DB 阻塞事件循环 | asyncio.to_thread |
| 12 | 缺测试 | test_chat_important_fixes.py |

---

## Important 修复（Phase 4 后）

| # | 问题 | 修复 |
|---|------|------|
| 14 | trend degraded summary 未进 LLM | orchestrator 按 summary 注入 |
| 15 | Swarm 无实时进度 | 逐 Skill skill_start + on_progress |
| 16 | 趋势 API 重复计算 | 复用 analyze_trends 结果 |
| 17 | created_at 解析 500 | `_parse_created_at()` |
| 18 | CI workflow 路径错误 | working-directory: backend |
| 19 | README API 路径错误 | /history 非 /messages |

---

## 前端修复

| 问题 | 修复 |
|------|------|
| 发送按钮无反应 | 自动 user_id，移除手动填写依赖 |
| UI 复杂 | ChatGPT 式单页 + 左侧栏 |
| 表单绑定 | addEventListener 替代 inline onsubmit |

---

## 遗留 Minor（可后续迭代）

- trend 触发词 Orchestrator vs Skill 不完全一致
- period_days 已加边界校验
- Eval 断言依赖 DISCLAIMER 字符串切片
- 生产环境需 JWT 认证
