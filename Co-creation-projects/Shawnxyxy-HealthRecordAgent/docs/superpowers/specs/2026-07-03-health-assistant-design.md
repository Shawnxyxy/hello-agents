# 健康助手（对话主入口）设计规格

**日期:** 2026-07-03  
**目标:** 将 HealthRecordAgent 升级为 Skills-Agent 两层架构 + Harness Engineering，以对话为主入口，支持对话内上传体检报告。

## 背景

- 目标岗位：AI/Agent 工程师 + 全栈/后端工程师
- 产品名：**健康助手**（非 Copilot 品牌名）
- 参照业界 Skills-Agent 两层架构、Harness Engineering、ReAct 编排

## 架构

```
Frontend (Chat UI)
    → POST /api/chat/sessions/{id}/messages (multipart + SSE)
Agent Layer (HealthAssistantOrchestrator)
    → ReAct / 规则路由 → Skill 调用
Skills Layer
    → report_analysis | diet_recommend | guideline_rag | memory_retrieve | safety_guard
Harness Layer
    → 安全规则 | 输出审查 | trace
Infrastructure
    → SQLite (会话 + 持久记忆) | Milvus (RAG, 可选)
```

## 交互

- 主界面：聊天窗口，默认 Tab
- 输入：文本 + 📎 附件（PDF / .txt）
- 上传报告：附件触发 `report_analysis` Skill，流式展示进度，完成后自然语言解读
- 追问：会话上下文保留 `last_report_task_id`
- 次要 Tab：「历史记录」保留；原档案/饮食 Tab 收进「高级模式」

## Skills 接口

```python
class SkillResult(BaseModel):
    skill_id: str
    success: bool
    data: dict
    summary: str
    trace: list[dict]
    degraded: bool = False
```

| Skill | 实现来源 |
|-------|----------|
| report_analysis | HealthAnalysisService |
| diet_recommend | DietMultiAgentPipeline |
| guideline_rag | rag.retriever |
| memory_retrieve | memory.store + Milvus |
| safety_guard | harness（新增） |

## API

- `POST /api/chat/sessions` — 创建会话
- `GET /api/chat/sessions/{id}/history` — 消息历史
- `POST /api/chat/sessions/{id}/messages` — 发消息（multipart），响应 SSE

SSE 事件：`skill_start` | `skill_progress` | `token` | `safety` | `done`

## Harness 安全

- 禁止明确诊断、禁止药物剂量
- 高危症状词 → 强制就医提醒
- 每条回复附加免责声明

## 分阶段交付

| Phase | 内容 |
|-------|------|
| P1 | Skill 层 + Harness |
| P2 | Orchestrator + Chat API + 会话 SQLite |
| P3 | 前端对话 UI |
| P4 | Agent Swarm + trend_compare + Eval |
| P5 | README + Docker Compose |

## 决策

- 会话存储：P1–P3 使用 SQLite，Redis 留 P5
- 旧 Tab：保留为「高级模式」，默认隐藏
