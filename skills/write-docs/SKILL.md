---
name: write-docs
description: >-
  技术写作路由：写、改、审任何技术文字——技术博客、技术方案、RFC、ADR、接口文档、表结构与迁移、
  操作指南、Runbook、README、PR 描述、周报、事故通报、IM 和邮件。用户提到去 AI 味、模仿文风
  或扫描 AI 腔时也触发。Use when writing, editing, or reviewing technical text: blog, design doc,
  RFC, API doc, schema, runbook, README, PR description, or removing AI flavor from text.
---

# write-docs

动笔前先锁定合同（写给谁、在哪读、读完能做什么），再按体裁加载对应 reference，最后去过 AI 味和事实回查。

## 1. 合同

动笔前能复述这一句：

> 写给〈谁〉，在〈什么场景〉读，读完要能〈做什么或判断什么〉；体裁是〈路由〉。

缺一项且无法从任务推断时，只问一个问题。默认值：同团队工程师，中文，Markdown。

## 2. 体裁

| 用户说 | 体裁 | 加载 |
|---|---|---|
| 博客、技术分享、复盘、发布文章 | `tech-blog` | `references/tech-blog.md` |
| 技术方案、设计文档、RFC、ADR、架构评审、选型 | `design-doc` | `references/design-doc.md` |
| 接口文档、API、OpenAPI、错误码、SDK 说明 | `api-doc` | `references/api-doc.md` |
| 表结构、数据字典、字段说明、迁移或 DDL 评审 | `schema-doc` | `references/schema-doc.md` |
| 使用指南、教程、快速开始、README、Runbook、FAQ | `howto` | `references/howto.md` |
| PR 描述、周报、事故通报、评审意见、IM、邮件、会议纪要 | `everyday` | `references/everyday.md` |
| 去 AI 味、模仿文风、扫描 AI 腔 | `de-ai` | `references/de-ai.md` |

体裁冲突时：要评审和拍板 → `design-doc`；读者要照做 → `howto`；只查字段和返回值 → `api-doc`；主体是表和迁移 → `schema-doc`；已经做完要讲证据和局限 → `tech-blog`；一屏以内且已有上下文 → `everyday`。

每次任务加载 `references/shared.md` + 一个体裁 reference，不要全部加载。

## 3. 工作流

1. **材料**：先把事实、引用、推测和缺口分开。无法推断的标「待补」，不编。
2. **写作**：按体裁 reference 写。用户给了格式或大纲就优先遵守，不为套模板重构。
3. **自检**：拿体裁 reference 的检查清单逐项过。不适用的项说明原因，不硬套。
4. **去 AI 味**：超 300 字的稿子必做。能跑脚本就跑：
   ```bash
   python3 ~/.agents/skills/write-docs/scripts/scan_ai_taste.py draft.md --profile all
   ```
   HIGH 必改，MEDIUM 逐条判断。三轮改不完，问题在提纲不在措辞。回去补证据。
5. **事实回查**：比对去 AI 味前后的数字、名称、链接、代码和限定条件。
6. **交付**：给稿子，单独列出待补信息、假设和未验证项。不附客套结尾。

## 4. 陷阱

- 去 AI 味后最常见的失败是数字或限定条件跟改前不一样。「大幅降低」→「降低了 X%」这种改法，原文如果有负载条件或时间范围，容易丢。第 5 步事实回查就是干这个的。
- 用户说「只用给的材料」时，体裁 reference 里的规范示例（RFC 9457 字段、OpenAPI 约定）不算当前 API 的事实。材料没写的写「材料未提及」，不拿规范当行为。
- 用户给了格式或大纲时，design-doc 的标准节、howto 的步骤结构都让步。不为套模板把用户的结构拆了重排。
- 材料不足时推断是允许的，但标清楚：「我们推测」「尚未验证」。不要为了读起来顺，把推测当成事实写进去。
