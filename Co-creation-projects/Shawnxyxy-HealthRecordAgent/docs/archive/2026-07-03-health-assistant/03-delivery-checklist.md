# 健康助手 v1 交付清单

**归档日期:** 2026-07-04

---

## 功能交付

| 能力 | 状态 | 验证方式 |
|------|------|----------|
| 对话 SSE 流式 | ✅ | E2E / 浏览器 |
| 上传 PDF/txt 报告 | ✅ | E2E 上传 sample_reports/report.txt |
| 报告多 Agent 分析 | ✅ | report_analysis Skill + One API |
| 追问加载上次报告 | ✅ | prior_report_context |
| Agent Swarm 并行 | ✅ | memory + RAG + trend |
| 趋势对比 Skill | ✅ | 关键词 / force_trend |
| Harness 安全审查 | ✅ | 免责声明 + 高危拦截 |
| ChatGPT 式 UI | ✅ | 侧边栏 + 自动 user_id |
| 历史会话列表 | ✅ | GET /chat/users/{id}/sessions |

---

## 自动化测试

```bash
cd backend
PYTHONPATH=. python -m pytest tests/ -v          # 20 passed
PYTHONPATH=. python scripts/run_harness_eval.py  # 3/3 passed
```

| 测试文件 | 用例数 | 覆盖 |
|----------|--------|------|
| test_report_analysis_skill.py | 5 | Skill 字段解析 |
| test_chat_important_fixes.py | 5 | 追问/PDF/DB 迁移 |
| test_phase4.py | 4 | Swarm / trend / eval |
| test_review_fixes.py | 6 | CR 修复项 |

---

## 运行环境

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| LLM | One API 或兼容 OpenAI 网关（`.env`） |
| Milvus | 可选 |
| 后端 | `uvicorn api.main:app --port 8000` |
| 前端 | `python3 -m http.server 5500` |

---

## 未交付 / 已知限制

- Redis 会话（设计为可选，未实现）
- Docker Compose（P5 待定）
- 生产级认证（当前为 Demo 级 auto user_id）
- 首份报告无法趋势对比（需 ≥2 次体检，符合设计）

---

## Git 状态（归档时）

- **分支:** `feature/health-record-agent`
- **提交:** `82b4ee7`
- **远程:** 已 push 至 `origin/feature/health-record-agent`
- **工作区:** clean
