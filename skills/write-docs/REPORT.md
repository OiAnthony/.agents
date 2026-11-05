# write-docs 调研报告：怎样写好 Web 全栈技术文档，以及怎样去掉 AI 味

日期：2026-11-04（UTC+8）
产物：`~/.agents/skills/write-docs/`（路由 skill + 9 份 reference + 扫描脚本 + 6 个模板）

<!-- ai-taste: off -->

## 1. 结论

1. **好的技术文章有一套共同结构**：用具体问题或数字开头 → 一句话定义核心术语 → 先讲朴素做法怎么失败 → 一节一个决定、标题写结论 → 证据紧挨判断（表格、消融、基线、方法论）→ 报告成本和负面结果 → 写明局限和未知。DeepSeek、Anthropic、OpenAI、Factory 四家的样本都符合这个模式。（高可信，6 篇原文拆解）
2. **DeepSeek Super-agent 文章值得学的是骨架，不是句子**：声明定预期；缺口带数字（3–5 个会话）；4 条可检验特征；模块、章节、总图编号三者一一对应；两极权衡；借用经典概念当场映射；实验含消融和成本，照报中性结果；开放问题收尾。不学它的长复合句和结尾的愿景段落。（高可信）
3. **体裁先于文笔**。Diátaxis 把文档按「行动/认知 × 学习/干活」分成教程、操作指南、参考、解释四类，一篇只做一类。API 文档和表结构文档是参考，要能查、能复制；设计文档要能拍板，核心是备选方案和权衡；博客要讲清做了什么、证据和局限。（高可信，Diátaxis + pstack technical-writing）
4. **参考类文档的事实源应该是机器可读的**：API 以 OpenAPI 为准，错误格式用 RFC 9457 Problem Details（`type`/`title`/`status`/`detail`/`instance`，字段错误用扩展 + JSON Pointer）；表结构以迁移文件为准，注释写进库，字典由 CI 生成和校验漂移。手写部分只写 schema 表达不了的东西：为什么、何时用、陷阱、每个索引服务哪条查询。（高可信）
5. **AI 味的根源是「向均值回归」加上没想清楚**。模型在缺少具体判断和证据时用最常见的模板填充，表现为空洞的重要性、均匀的句长段长、过度格式化。脚本能查词汇和句式，查不了内容空洞；后者只能回到提纲补证据。（高可信，Wikipedia: Signs of AI writing + 本地 write/humanizer skill）
6. **gpt-6.1-sol 的口癖有官方清单可依**：OpenAI《Using GPT-6》指南点名的 slop 包括「Bottom Line:」「In short:」「The simplest mental model is:」、delve/foster/leverage/genuinely、「This isn't about X. It's about Y.」、Question? Answer. 节奏、声明自己没改什么、「X, not Y」框架、过度格式化、跨会话重复短语。Wikipedia 补充 GPT-6 时代高频词（quietly、steady、dependable、multifaceted 等）和短句均匀（8–20 词）。gpt-6.1-sol 是否完全继承，未单独验证。（官方部分高可信；推到 6.1 中可信）
7. **deepseek-flash 的证据弱**：只找到个例报告（冗长、不守字数、正文里出现「wait / let me reconsider」式的推理外泄、反复重述结论）。中文口播腔（说白了、一句话总结、核心逻辑）是启发式，未经语料验证。因此脚本对它的规则偏保守，并提供 `--ngrams` 让你用自己的产出校准。（低可信）
8. **风格模仿比禁用词表更有效**：先从 1–3 篇样例提取风格卡（人称、句长、段首句、标题写法、证据习惯、格式习惯、「从不」清单、代表句），再写。提示用正面描述，提示本身的格式会影响输出格式（想要段落就别用一长串项目符号写提示），禁用项放最后。gpt 侧重压格式化和标签开头，deepseek 侧重「只输出正文」、长度上限和输出锚点，不加「一步一步思考」。（Anthropic 和 OpenAI 的提示建议中高可信；DeepSeek 部分来自检索综合，中低可信）
9. **现有去 AI 味工具收敛到同一套机制**：分级严重度 + 密度阈值 + 非零退出码（crypdick/unslop、mikefluff、deslop）；句长变异系数作为统计信号（anti-ai-tell：「泛泛是方差不足」）；中文工具分词汇/句式/篇章三层（de-aigc-ch、humanize-chinese）；改写分「可改写」和「空心」两类，最多三轮（isatimur/de-slop）；明确反对矫枉过正（humanizer-chinese）。本 skill 的脚本照此实现。（高可信，基于仓库说明和检索摘要，未逐行读源码）
10. **要防的是矫枉过正**：故意加口语、错字、金句收尾、硬拆句、同义词轮换，都是新的假。目标是准确和具体，不是「不像 AI」。检测器和人工识别都不可靠，扫描分数只是写作质量提示，不能当「是否 AI 写的」的证据。（高可信）

## 2. 产物说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 一句话锁合同 → 路由表 + 冲突判定 → 读多少 → 7 步流程（800 字以上必过去AI味关卡）→ 与其他 skill 的边界 → 完成标准 |
| `references/shared.md` | 合同、证据三档、封闭材料模式、术语、标题、段落、中文排版 |
| `references/tech-blog.md` | 三种骨架（探索型/实践型/发布型）、实验清单、诚实现状句式、不要学的 |
| `references/design-doc.md` | 四种模式（深度模板指向 writing-technical-design）、必备节、一页方案、ADR-lite、权衡写法、Web 全栈检查 |
| `references/api-doc.md` | OpenAPI 为事实源、端点要素、RFC 9457、分页/幂等/限流/版本/时间金额/空值 |
| `references/schema-doc.md` | 单表要素、设计检查、索引对查询、expand/contract 迁移（锁、验证 SQL、回滚） |
| `references/howto.md` | Diátaxis 罗盘、How-to/Tutorial/README/Runbook/FAQ |
| `references/everyday.md` | PR、周报、事故通报、评审意见、IM、会议纪要、邮件 |
| `references/de-ai.md` | 成因、三层诊断、两个模型画像、风格模仿协议和提示骨架、改写循环、防矫枉过正、个人口癖库 |
| `references/benchmarks.md` | 6 篇标杆拆解和共同模式 |
| `scripts/scan_ai_taste.py` + `patterns.yaml` | 59 条规则（中文 32、英文 9、残留 2、gpt-6.1-sol 8、deepseek-flash 5、结构 8），零依赖 |
| `assets/` | 博客骨架、API 端点、表结构、Runbook、PR 描述、风格卡 |

## 3. 未决问题

- gpt-6.1-sol 与 GPT-6 的口癖差异没有公开资料；建议用 20 篇以上实际产出跑 `--ngrams` 补充 G 系列规则。
- deepseek-flash 的中文规则（D03）是启发式，同样需要语料校准，可能误报。
- X 帖子 https://x.com/DeepSeekHarness/status/2116857257245987236 抓取返回 403，内容未核实；推测是同一篇文章的发布帖。
- de-aigc-ch 的 detect.py（raw 链接 404）和 crypdick/unslop 页面未能读取源码，相关结论基于检索摘要。
- Factory 大任务文章的数字（35.8% → 90.3%）来自检索摘要和二手报道，未读到原文全文。

## 4. 来源

标杆文章
- DeepSeek Harness，Super-agent 设计探索：https://mp.weixin.qq.com/s/zoS7GlReWPhfCjENGxXCdg（已读全文）
- DeepSeek Harness X 帖：https://x.com/DeepSeekHarness/status/2116857257245987236（403，未读）
- Anthropic，Harness design for long-running application development（2026-03-24）：https://www.anthropic.com/engineering/harness-design-long-running-apps
- Anthropic，Building a C compiler with a team of parallel Claudes（2026-02-05）：https://www.anthropic.com/engineering/building-c-compiler
- OpenAI，Harness engineering（2026-02-11）：https://openai.com/index/harness-engineering/
- OpenAI，Unrolling the Codex agent loop：https://openai.com/index/unrolling-the-codex-agent-loop/（仅摘要）
- Factory，Droid 1.0: Building a Frontier Harness（2026-10-29）：https://factory.com/news/frontier-harness
- Factory，What it Takes for Coding Agents to Complete Large Software Tasks（2026-08-27）：https://factory.com/news/what-it-takes-for-coding-agents-to-complete-large-software-tasks（摘要 + 二手）

文档体裁与规范
- Diátaxis：https://diataxis.fr/
- RFC 9457 Problem Details for HTTP APIs：https://www.rfc-editor.org/rfc/rfc9457
- GOV.UK，Writing API reference documentation：https://www.gov.uk/guidance/writing-api-reference-documentation
- Google developer documentation style guide：https://developers.google.com/style
- pstack `technical-writing`、`unslop`、`poteto-mode`（本机 skill）

去 AI 味
- Wikipedia: Signs of AI writing：https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- OpenAI，Using GPT-6（latest model guide）：https://developers.openai.com/api/docs/guides/latest-model
- r/DeepSeek 关于 deepseek-v4-flash 冗长输出的帖子（个例，低可信）
- Anthropic prompting best practices（检索综合，中可信）
- 工具：crypdick/unslop、MikkoParkkola/anti-ai-tell、mikefluff/skills、adamcharnock/deslop、isatimur/de-slop、swaylq/humanize-chinese、hongcha1101/de-aigc-ch、B1lli/remove-ai-flavor-writing-skill、zero-click/avoid-ai-writing-zh、jiji262/humanizer-chinese（均在 GitHub）

本机 skill
- `~/.agents/skills/writing-technical-articles`、`writing-technical-design`、`write`（含 `references/write-zh.md`）、`humanizer`、`kami`
<!-- ai-taste: on -->
