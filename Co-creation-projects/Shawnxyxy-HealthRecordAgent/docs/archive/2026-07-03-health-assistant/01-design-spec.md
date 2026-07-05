# 健康助手（对话主入口）设计规格

**版本:** v1（归档）  
**日期:** 2026-07-03  
**归档更新:** 2026-07-04  

## 背景

- **目标岗位:** AI/Agent 工程师 + 全栈/后端工程师  
- **产品名:** 健康助手（非 Copilot 品牌名）  
- **参照:** Skills-Agent 两层架构、Harness Engineering、规则路由 Orchestrator  

## 架构

```
Frontend (ChatGPT 式 Chat UI + 左侧栏)
    → POST /api/chat/sessions/{id}/messages (multipart + SSE)
Agent Layer (HealthAssistantOrchestrator)
    → 规则路由 → Skill 调用 / Agent Swarm 并行
Skills Layer
    → report_analysis | diet_recommend | guideline_rag | memory_retrieve
    → trend_compare | safety_guard
Harness Layer
    → 安全规则 | 输出审查 | Eval Suite
Infrastructure
    → SQLite (会话 + 持久记忆) | Milvus (RAG, 可选，失败回退 SQL)
```

## 交互（最终实现）

- **主界面:** 全屏对话窗口，底部输入框，类似 ChatGPT  
- **左侧栏:** 历史会话列表、「新对话」、用户设置（显示名称 / 自动 user_id）  
- **输入:** 文本 + 📎 附件（PDF / .txt，≤10MB）  
- **上传报告:** 附件触发 `report_analysis` Skill，SSE 展示进度，LLM 汇总解读  
- **追问:** 会话保留 `last_report_task_id`，无附件时加载已分析报告上下文  
- **趋势:** 关键词或上传报告后 `force_trend` 触发 `trend_compare`  
- **已移除:** 顶部 Tab、手动用户 ID、开发者模式、高级模式 Tab（后端能力仍保留）  

## Skills 接口

```python
class SkillContext(BaseModel):
    user_id: str
    session_id: str
    message: str = ""
    report_text: Optional[str] = None
    last_report_task_id: Optional[str] = None
    extra: dict = {}

class SkillResult(BaseModel):
    skill_id: str
    success: bool
    data: dict
    summary: str
    trace: list[dict]
    degraded: bool = False
```

| Skill | 实现来源 | 触发条件 |
|-------|----------|----------|
| report_analysis | HealthAnalysisService（内层 Plan-and-Execute 多 Agent） | 有 report 附件 |
| memory_retrieve | rag.retriever | Swarm 默认每轮 |
| guideline_rag | rag.retriever | Swarm 默认每轮 |
| trend_compare | TrendAnalysisService | 关键词 / force_trend / Swarm |
| diet_recommend | DietRecommendService（内层多 Agent 流水线） | 饮食关键词 |
| safety_guard | harness.output_reviewer | 每轮 LLM 输出后 |

---

## Skills 详解

### 设计模式

| 类型 | Skill | 说明 |
|------|-------|------|
| **重型 Skill** | report_analysis、diet_recommend | 整包封装现有 Multi-Agent 流水线，对外一个 SkillResult |
| **轻量 Skill** | memory_retrieve、guideline_rag、trend_compare、safety_guard | 单次 RAG / 趋势分析 / 规则审查 |

Specialist Agent **未**各自拆成 Skill；报告/饮食域内仍保留 Plan-and-Execute 串行编排。

### 1. report_analysis

- **功能:** 解析体检报告，Planner + Specialist 串行（指标 → 风险 → RAG → 建议 → 汇总）
- **文件:** `backend/skills/report_analysis_skill.py` → `backend/service/health_analysis.py` → `backend/agents/*`
- **触发:** Orchestrator 检测 `ctx.report_text` 非空

### 2. diet_recommend

- **功能:** 饮食日志解析 + 多阶段推荐（营养师/教练/习惯）
- **文件:** `backend/skills/diet_recommend_skill.py` → `backend/service/diet_recommend_service.py`
- **触发:** 消息匹配 `DIET_PATTERN`，或 `ctx.extra.force_diet`

### 3. memory_retrieve

- **功能:** 检索用户私有历史（体检、饮食、Reflect 反馈）
- **文件:** `backend/skills/memory_retrieve_skill.py` → `backend/rag/retriever.py`（scenario=`health_chat`）
- **触发:** Swarm 每轮默认并行

### 4. guideline_rag

- **功能:** 检索通用健康知识 / 指南片段
- **文件:** `backend/skills/guideline_rag_skill.py` → `backend/rag/retriever.py`（scenario=`health_guideline`）
- **触发:** Swarm 每轮默认并行

### 5. trend_compare

- **功能:** 多次体检报告指标对比与趋势汇总
- **文件:** `backend/skills/trend_compare_skill.py` → `backend/service/trend_analysis.py`
- **触发:** 关键词 / 上传报告后 `force_trend`；亦可通过 REST `GET .../trend_analysis` 独立调用

### 6. safety_guard

- **功能:** Harness 审查 LLM 草稿（高危拦截、禁止诊断/剂量、免责声明）
- **文件:** `backend/skills/safety_guard_skill.py` → `backend/harness/output_reviewer.py` → `safety_rules.py`
- **触发:** 每轮 LLM 生成 draft 之后必跑

---

## Skill 调用链路与代码路径

### 总入口（对话）

```
frontend/chat.js  sendChatMessage()
    → POST /api/chat/sessions/{id}/messages   [multipart + SSE]
        backend/api/routes/chat.py :: send_message()
            → HealthAssistantOrchestrator.stream_response()
                backend/chat/orchestrator.py
```

### 注册与实例化

```
get_skill_registry()
    backend/skills/registry.py
        → ReportAnalysisSkill / DietRecommendSkill / …（单例注册表）
```

### 三种调用方式

| 方式 | 函数 | 路径 | 用于 |
|------|------|------|------|
| **安全单调用** | `run_skill_safe(skill, ctx)` | `backend/chat/skill_runner.py` | report_analysis（带进度）、diet、safety_guard |
| **Swarm 并行** | `run_skill_swarm(registry, ids, ctx)` | `backend/chat/swarm.py` | memory_retrieve + guideline_rag + trend_compare |
| **非 Skill 上下文** | `build_prior_report_context()` | `backend/chat/report_context.py` | 追问时加载上次报告（非 registry 内 Skill） |

统一执行路径：

```
run_skill_safe / run_skill_swarm
    → skill.run(ctx, on_progress=...)
        → 各 backend/skills/*_skill.py
            → service / rag / harness 下层
```

### Orchestrator 单轮顺序

```
stream_response()  [backend/chat/orchestrator.py]

1. 有附件?
   └─ _run_skill_with_live_progress(report_analysis)
       └─ run_skill_safe → ReportAnalysisSkill.run()
       └─ 成功 → touch_chat_session(last_report_task_id); force_trend=True

2. 无附件但有 last_report_task_id?
   └─ build_prior_report_context()  [非 Skill]

3. Agent Swarm（asyncio.gather 并行）
   └─ run_skill_swarm(["memory_retrieve", "guideline_rag", (+ trend_compare?)])
       └─ 每个 → run_skill_safe → *.run()

4. 饮食关键词?
   └─ run_skill_safe(diet_recommend)

5. LLM 汇总 skill_results[].summary → draft

6. run_skill_safe(safety_guard, extra={draft_response: draft})
   └─ SafetyGuardSkill → review_assistant_output()

7. SSE token 流式输出 final_text → done
```

### 独立 REST 入口（不经 Orchestrator）

| 能力 | 路径 |
|------|------|
| 趋势分析 | `backend/api/routes/health.py` → `TrendAnalysisService` |
| 饮食推荐 | `backend/api/routes/diet.py` → `DietRecommendService` |
| 报告分析 | `backend/api/routes/health.py` → `HealthAnalysisService` |

### 相关文件索引

| 职责 | 路径 |
|------|------|
| Skill 基类 | `backend/skills/base.py` |
| Skill 注册表 | `backend/skills/registry.py` |
| 对话编排 | `backend/chat/orchestrator.py` |
| Swarm | `backend/chat/swarm.py` |
| 安全执行 | `backend/chat/skill_runner.py` |
| Chat API | `backend/api/routes/chat.py` |
| FastAPI 挂载 | `backend/api/main.py` |
| Harness 规则 | `backend/harness/safety_rules.py` |
| Harness 审查 | `backend/harness/output_reviewer.py` |
| Eval | `backend/harness/eval_runner.py`, `evals/safety_cases.json` |


| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/sessions` | 创建会话 |
| GET | `/api/chat/sessions/{id}` | 会话详情 |
| GET | `/api/chat/sessions/{id}/history` | 消息历史 |
| GET | `/api/chat/users/{id}/sessions` | 用户会话列表 |
| POST | `/api/chat/sessions/{id}/messages` | 发消息（multipart），SSE 响应 |
| GET | `/api/health/users/{id}/trend_analysis` | 趋势 REST API |

**SSE 事件:** `skill_start` · `skill_progress` · `token` · `safety` · `error` · `done`

## Harness 安全

- 禁止明确诊断、禁止药物剂量推荐  
- 高危症状词 → 强制就医提醒（含 120 / 急诊）  
- 每条回复附加免责声明  
- Eval: `evals/safety_cases.json` + `backend/harness/eval_runner.py`  

## 分阶段交付

| Phase | 内容 | 状态 |
|-------|------|------|
| P1 | Skill 层 + Harness | ✅ |
| P2 | Orchestrator + Chat API + SQLite 会话 | ✅ |
| P3 | ChatGPT 式前端 + SSE 客户端 | ✅ |
| P4 | Agent Swarm + trend_compare + Eval + CI | ✅ |
| P5 | Redis 会话 / Docker Compose | ⏭ 可选 |

## 决策记录

- 会话存储：SQLite；Redis 留作可选扩展  
- 用户身份：前端自动生成 `user-{uuid}`，localStorage 持久化  
- Orchestrator 路由：规则匹配（非 LLM 意图识别）  
- Milvus 不可用：RAG 回退 SQL 列表，不阻断主流程  
