# 健康助手 Implementation Plan（归档）

**Goal:** 以「健康助手」对话为主入口，Skills-Agent 两层架构 + Harness 安全层，支持对话内上传体检报告。

**Architecture:** Orchestrator 规则路由 Skill；health/diet 流水线下沉为 Skill；SQLite 会话；SSE 流式响应。

**Tech Stack:** FastAPI, Pydantic, SQLite, hello-agents LLM, Milvus（可选）

---

## Phase 1 — Skill + Harness ✅

- [x] `backend/skills/base.py` — SkillContext / SkillResult / BaseSkill
- [x] `backend/skills/*_skill.py` — report, diet, memory, guideline_rag, safety_guard, trend_compare
- [x] `backend/harness/safety_rules.py` + `output_reviewer.py`

## Phase 2 — Orchestrator + API ✅

- [x] `backend/memory/store.py` — chat_sessions / chat_messages
- [x] `backend/chat/orchestrator.py` — SSE 编排
- [x] `backend/chat/skill_runner.py` — Skill 安全执行
- [x] `backend/chat/report_context.py` — 追问上下文
- [x] `backend/api/routes/chat.py` — REST + multipart + SSE
- [x] `backend/api/main.py` — 挂载 chat router

## Phase 3 — Frontend ✅

- [x] ChatGPT 式单页对话（`frontend/index.html`）
- [x] 左侧栏：历史会话 / 新对话 / 用户设置
- [x] `frontend/chat.js` — SSE 客户端、自动 user_id
- [x] `frontend/app.js` — 侧边栏与会话列表
- [x] `frontend/style.css` — ChatGPT 风格样式

## Phase 4 — Swarm + Trend + Eval ✅

- [x] `backend/chat/swarm.py` — Agent Swarm 并行
- [x] `backend/skills/trend_compare_skill.py`
- [x] `backend/service/trend_analysis.py`
- [x] `GET /api/health/users/{user_id}/trend_analysis`
- [x] `backend/harness/eval_runner.py` + `evals/safety_cases.json`
- [x] `.github/workflows/harness-eval.yml`
- [x] README 架构图更新
- [ ] Redis 会话（可选，未实现）

## Phase 5 — 可选后续

- [ ] Docker Compose 一键启动
- [ ] Redis 会话层
- [ ] 合入 upstream hello-agents 社区 PR

---

## 关键文件清单

| 模块 | 路径 |
|------|------|
| 编排 | `backend/chat/orchestrator.py` |
| Swarm | `backend/chat/swarm.py` |
| Skill 注册 | `backend/skills/registry.py` |
| Chat API | `backend/api/routes/chat.py` |
| 前端 | `frontend/index.html`, `chat.js`, `app.js` |
| 测试 | `backend/tests/test_*.py`（4 文件，20 用例） |
