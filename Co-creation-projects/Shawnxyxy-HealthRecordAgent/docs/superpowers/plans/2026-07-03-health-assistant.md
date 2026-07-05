# 健康助手（对话主入口）Implementation Plan

> **已归档：** 正式版本见 [`docs/archive/2026-07-03-health-assistant/02-implementation-plan.md`](../archive/2026-07-03-health-assistant/02-implementation-plan.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以「健康助手」对话为主入口，Skills-Agent 两层架构 + Harness 安全层，支持对话内上传体检报告。

**Architecture:** Orchestrator 路由 Skill；现有 health/diet 流水线下沉为 Skill；SQLite 会话；SSE 流式响应。

**Tech Stack:** FastAPI, Pydantic, SQLite, hello-agents LLM, 现有 RAG/Milvus

---

## Phase 1 — Skill + Harness ✅

- [x] `backend/skills/base.py` — SkillContext / SkillResult / BaseSkill
- [x] `backend/skills/*_skill.py` — report_analysis, diet_recommend, memory, guideline_rag, safety_guard
- [x] `backend/harness/safety_rules.py` + `output_reviewer.py`

## Phase 2 — Orchestrator + API ✅

- [x] `backend/memory/store.py` — chat_sessions / chat_messages 表
- [x] `backend/chat/orchestrator.py` — SSE 编排
- [x] `backend/api/routes/chat.py` — REST + multipart + SSE
- [x] `backend/api/main.py` — 挂载 chat router

## Phase 3 — Frontend ✅

- [x] ChatGPT 式单页对话 + 左侧栏历史会话
- [x] `frontend/chat.js` — SSE 客户端
- [x] `frontend/style.css` — 对话样式
- [x] `frontend/app.js` — 侧边栏与会话列表

## Phase 4 — Swarm + Trend + Eval ✅

- [x] `backend/chat/swarm.py` — Agent Swarm 并行 Skill
- [x] `backend/skills/trend_compare_skill.py` + `GET /api/health/users/{user_id}/trend_analysis`
- [x] `backend/harness/eval_runner.py` + `evals/safety_cases.json` + `.github/workflows/harness-eval.yml`
- [ ] Redis 会话（可选，未实现）
- [x] README 架构图更新
