---
name: write-docs
description: >-
  Web 全栈技术写作路由：技术博客/工程博客、技术方案/设计文档、接口文档/API 文档、表结构/数据字典/迁移说明、
  使用指南/教程/Runbook/README、日常写作（PR 描述、周报、事故通报、评审意见、IM 消息、邮件），
  以及去AI味（风格模仿 + 静态扫描脚本，针对 gpt-6.1-sol 和 deepseek-flash）。
  中文为主，术语保留英文。Use for: write docs, tech blog, design doc, API doc, schema doc, how-to, runbook,
  PR description, de-AI / remove AI taste / humanize, 写文档, 写博客, 技术方案, 接口文档, 表结构, 使用指南, 去AI味.
when_to_use: >-
  用户要写、改、审任何技术文档或工程文字，或要求去AI味、模仿某种文风、扫描AI腔时。
  深度设计评审模板交给 writing-technical-design；中文长文的语气和配图交给 writing-technical-articles；
  纯润色交给 write 或 humanizer。
---

# write-docs

一个路由：先锁定写作合同，再按体裁读一份 reference，最后过去AI味关卡。只读当前任务需要的那一份。

## 1. 一句话锁定合同

动笔前写出一行（可以只在心里写，但要能复述）：

> 写给〈谁〉，在〈什么场景〉读，读完要能〈做什么或判断什么〉；体裁是〈路由〉；语言〈中文为主，术语英文〉。

缺一项且猜不出来时，问一个问题，只问一个。默认值：读者是同团队工程师，中文，Markdown。

## 2. 路由

| 用户说 | 路由 | 读 |
|---|---|---|
| 写篇博客、技术分享、复盘长文、发布文章、工程博客 | tech-blog | `references/tech-blog.md` |
| 技术方案、设计文档、RFC、ADR、架构评审、选型 | design-doc | `references/design-doc.md` |
| 接口文档、API 文档、OpenAPI、错误码、SDK 说明 | api-doc | `references/api-doc.md` |
| 表结构、建表、数据字典、字段说明、迁移/DDL 评审 | schema-doc | `references/schema-doc.md` |
| 使用指南、教程、快速开始、README、操作手册、Runbook、FAQ | howto | `references/howto.md` |
| PR 描述、周报、日报、事故通报、评审意见、IM 消息、邮件、会议纪要 | everyday | `references/everyday.md` |
| 去AI味、太像 AI 了、模仿这篇的风格、按我的文风写、扫一下 AI 腔 | de-ai | `references/de-ai.md` |

信号冲突时：

| 信号 | 判给 |
|---|---|
| 要评审、要拍板、有备选方案 | design-doc（即使用户说「写篇文章」） |
| 已经做完，讲做了什么和学到什么，读者在团队外 | tech-blog |
| 读者要照着一步步做 | howto；只查字段和返回值则是 api-doc |
| 主体是表、字段、索引、迁移 | schema-doc；接口和表都有，按读者先查哪个定主路由，另一个做附录 |
| 一屏以内、读者已有上下文 | everyday |
| 用户给了参考文章或说「像 XX 那样写」 | 先读 de-ai 的风格模仿协议，再读体裁路由 |
 
一份交付物同时包含多个目的时，按主要读者的首要动作选一个主路由；把另一目的拆成附录或链接，不把不同体裁的检查清单硬拼在同一篇里。

所有路由共用 `references/shared.md`（合同、证据、术语、标题、段落）。写长文前读一次。
需要模仿标杆结构时，读 `references/benchmarks.md`；普通技术博客不必加载它。

## 3. 读多少

- 一屏以内的日常文字：只读 everyday.md 对应小节。
- 单篇文档：shared.md + 一个路由文件 + 对应的 `assets/` 模板。
- 探索型或对外发布的技术博客：再读 de-ai.md；只有需要模仿标杆结构时才读 benchmarks.md。
- API、schema、howto 和 everyday 不因篇幅自动加载 benchmarks.md；用户明确要求标杆风格时再读。
- 不要为了「全面」一次读完所有 reference。

## 4. 通用流程

1. **材料**：把事实分成已测、已引用、推测和缺口；列出数字、代码、链接与条件。缺的标「待补」，不编。用户说「只用我给的材料」时进入封闭材料模式（见 shared.md）。
2. **带证据的提纲**：每个标题写成一句结论，下面挂支撑它的证据。没有证据的节删掉或标为假设。
3. **成稿**：按路由模板写。先写最难的一节（通常是权衡或实验），开头最后写。
4. **结构自检**：按路由文件末尾的检查清单逐项过。
5. **去AI味**：正文超过约 800 字，或用户提到 AI 味，或草稿由模型生成时，必须过这一关：
   ```bash
   python3 ~/.agents/skills/write-docs/scripts/scan_ai_taste.py draft.md --profile gpt-6.1-sol   # 或 deepseek-flash / all
   ```
   有 HIGH 就改，改完再扫，最多三轮。规则和改法见 `references/de-ai.md`。脚本只是 lint：扫干净不等于写得好。
6. **事实核对**：对比改写前后的数字、名称、链接、代码，确认去AI味没有改动事实。
7. **交付**：给出成稿；说明哪些是待补或假设；不附客套结尾。

## 5. 与其他 skill 的边界

| 需求 | 交给 |
|---|---|
| 正式评审方案、架构探索的完整模板 | `writing-technical-design`（用它的 `assets/`，这里不复制） |
| 中文长文的语气、节奏、配图 | `writing-technical-articles` |
| 已成稿，只要润色或标点检查 | `write`（按它自己的 punctuation gate 检查）或 `humanizer` |
| 英文开发者文档的风格细则 | pstack `technical-writing`（Diátaxis + Google style） |
| 英文去 slop 的规则编号 | pstack `unslop` |

本 skill 负责：选体裁、给骨架、给体裁专属的检查清单、跑去AI味扫描和改写循环。

## 6. 完成标准

- 合同的四项都能从成稿里找到答案。
- 每个标题是结论；每节只有一个结论。
- 每个数字有来源或测量条件；每个「更快」「更稳」有对照。
- 体裁检查清单全部通过。
- 扫描无 HIGH；MEDIUM 已逐条判断（保留的说得出理由）。
- 改写前后事实一致。

## 文件

```
SKILL.md
references/  shared · tech-blog · design-doc · api-doc · schema-doc · howto · everyday · de-ai · benchmarks
scripts/     scan_ai_taste.py · patterns.yaml · README.md · samples/
assets/      tech-blog-skeleton · api-endpoint · schema-table · runbook · pr-description · style-contract
```
