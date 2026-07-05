# 生产级体检报告解析模块 — 设计规格

**日期:** 2026-07-05  
**状态:** Approved（头脑风暴共识）  
**关联:** [健康助手设计](./2026-07-03-health-assistant-design.md)

## 头脑风暴决策摘要

| 维度 | 决策 |
|------|------|
| 目标 | 扛得住面试「格式各种各样怎么办」 |
| 格式档位 | **B**：txt + 文字 PDF + 表格 + 扫描 PDF（OCR） |
| OCR | **本地 PaddleOCR**，P2 optional |
| 图片 / VLM | **不做** |
| 指标名 | **C**：`indicator_catalog.yaml` + LLM 兜底 |
| 指标值抽取 | **A**：规则优先 + LLM 补缺失项 |
| Skill 边界 | 解析是 **`report_analysis` Skill 内 Stage 0**；代码独立 `report_parsing/` 模块 |

## Skill 内两阶段

```
report_analysis Skill（对外唯一入口）
  Stage 0  ReportParsingPipeline  → ParsedReport
  Stage 1  HealthAnalysisService   → Plan-and-Execute Agents
```

Orchestrator 仍只路由 `report_analysis`，不新增 `report_parse` Skill。

## 架构

```
Upload (txt/pdf bytes)
  → FormatRouter → Extractor (txt / pdfplumber text+tables)
  → RuleStructurer → LLMStructurer (补全) → Normalizer (词表)
  → ParseValidator → ParsedReport
  → HealthAnalysisService → HealthIndicatorAgent（解读型）
```

## 模块路径

`backend/service/report_parsing/` — 见仓库实现。

## 分期

- **P0（已完成）**：Pipeline + 词表 + Rule + LLM 接口 + Skill/health 集成
- **P1（已完成）**：golden fixture、前端 parse_quality 展示、`GET/POST /health/parse`
- **P2（已完成）**：PaddleOCR 可选模块 + `OCR_ENABLED` 配置；扫描 PDF 自动 fallback

## 面试话术

> 「对外一个 report_analysis Skill，对内 Parse→Analyze 两阶段。异构文档先归一成带 canonical_code 的 ParsedReport，LLM 不做唯一解析器；词表可单测，LLM 只补规则覆盖不到的项。」
