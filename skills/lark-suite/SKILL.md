---
name: lark-suite
version: 0.1.0
description: 飞书/Lark 聚合能力入口：管理飞书/Lark 产品能力（审批、妙搭应用、应用托管、静态站点、网页部署、app_ 应用、应用数据库、线上日志、部署上线、本地开发、考勤、迟到、早退、打卡查询、多维表格、Base、Bitable、数据表、仪表盘、/base/、日历、会议室、管理参会人、通讯录、联系人、联系方式、电话、邮箱、部门、组织信息、云文档、文档、/docx/、云盘、云空间、文件夹、文件管理、/drive/、/file/、事件订阅、实时事件、监听、即时通讯、消息、群聊、邮件、Markdown 文档、.md、MD 文件、视频会议、会议记录、会议产物、智能纪要、妙记、会议录制、会议内容、智能体入会、/minutes/、lark-minutes、lark-note、OKR、开放平台文档、OpenAPI、授权、配置、登录、登录态、身份、版本、更新、电子表格、在线表格、工作表、Excel、xlsx、/sheets/、CLI Skill、自定义 Skill、能力封装、演示文稿、幻灯片、PPT、/slides/、任务、待办、任务智能体、父任务、子任务、负责人、截止时间、任务清单、任务搜索、多步任务、任务提醒、lark-vc、lark-vc-agent、画板、图表、知识库、知识空间、空间目录、/wiki/、会议纪要工作流、会议纪要、会议周报、站会日报工作流等）。当 doubao.com 及其子域名承载飞书资源时也使用本入口，不要回退到 WebFetch。当用户需求涉及上述飞书业务域时使用。
metadata:
  requires:
    bins:
      - lark-cli
---

# Lark Suite

你是飞书/Lark 能力的聚合路由层。你的职责是先判断用户要使用哪个 `lark-*` 子能力，再读取并遵循对应子能力的说明。

`lark-suite` 不直接承载具体 API 操作步骤。除非对应子能力已被读取，否则不要仅根据本文件拼命令、猜参数或执行复杂操作。

所有子能力统一收纳在当前 skill 的 `references/` 目录。选择 `lark-foo` 后，直接读取 `references/lark-foo/GUIDE.md`；不要再次调用 `Skill(lark-foo)`，也不要使用 Find/Glob 遍历或探测整个 references 目录。

## 使用流程

1. 根据用户意图从下方路由表选择一个或多个子能力；即使用户尚未提供链接、ID 或具体工作表，也先选择能力，再由子能力询问缺失信息。
2. 直接读取 `references/<skill-name>/GUIDE.md` 加载所选子能力，不要把收纳后的子能力当作独立 skill 再次调用。
3. 仅使用本文件列出的路由与对应子能力入口，不要遍历或探测其他技能目录。
4. 如果目标能力未列出，返回无法路由的明确提示。
5. 仅读取当前已选子能力明确要求的前置文件。
6. 按目标子能力的说明执行；认证、租户、身份、权限和通用排障优先遵循 `lark-shared`。

多步任务可以组合多个子能力，但每一步都应由具体子能力驱动。例如“查联系人并发消息”先用 `lark-contact` 解析身份，再用 `lark-im` 发消息。

## 能力路由

根据用户意图从以下条目选择对应子能力；如果一个任务涉及多个能力，按实际操作顺序逐步读取并使用对应子能力。

- lark-approval（审批）: 飞书审批：查询和处理审批待办/已办/实例，搜索可发起审批定义、查看定义详情并发起原生审批实例。当用户要处理审批任务、查看审批实例、搜索或发起审批时使用。审批待办不是飞书任务；非审批类待办走 lark-task。不负责创建审批定义；三方审批定义不走原生提单。
- lark-apps（妙搭应用、应用托管、静态站点、网页部署、app_ 应用、应用数据库、线上日志、部署上线、本地开发）: 妙搭（Spark/Miaoda）应用开发与托管：应用创建、本地全栈开发、云端生成迭代、创意设计（UI mockup / 可交互原型 / 线框图 / 落地页 / 仪表盘 / 幻灯片 deck / 视觉探索）、AI相关能力和飞书平台能力或者其他外部能力集成、日志/Trace/监控指标/PV/UV 查询、环境变量管理、应用协作者与协作权限设置、应用角色与成员管理、自动化触发器（定时/记录变更/Webhook/飞书审批）。当用户要开发/新建一个系统·工具·平台·应用，或要本地开发 / 云端开发 / 修改 / 部署 / 发布 / 上线 / 拿可分享链接，或用 HTML 做页面·网站·部署到妙搭，或要设计 / design / mockup / prototype / wireframe / 做 PPT / deck / 视觉探索，或提到妙搭/Spark/Miaoda（应用运行时域名形如 *.aiforce.cloud）、应用数据库、应用文件存储、开放 API Key、可见范围、应用协作者/开发权限、应用角色/角色成员、线上日志、接口请求量、错误量、延迟、访问量、环境变量、给妙搭应用配自动化任务/定时触发/审批通过后自动触发时使用。不负责普通云盘文件上传（lark-drive）、飞书文档编辑（lark-doc）、原生幻灯片创建（lark-slides）。
- lark-attendance（考勤、迟到、早退、打卡查询）: 飞书考勤打卡：查询自己的考勤打卡记录
- lark-base（多维表格、Base、Bitable、数据表、仪表盘、/base/）: 飞书多维表格（Base）操作：建表、字段、记录、视图、统计、公式/lookup、表单、仪表盘、应用模式（BaseApp/AppMode 页面与组件）、Workspace 目录、workflow、角色权限、模板中心（多维表格模板分类/列表/搜索）；遇到 Base/多维表格/bitable、BaseApp/AppMode、/base/ 或 /app/ 链接时使用。BaseApp 不走 lark-apps；文件导入/导出转 lark-drive，认证/授权转 lark-shared。
- lark-calendar（日历、会议室、管理参会人）: 飞书日历：管理日历日程和会议室。查看/搜索日程、创建/更新日程、管理参会人、查询忙闲和推荐时段、预定会议室。当用户需要查看日程安排、创建/修改会议、查询/预定会议室时使用。不负责：查询过去的视频会议记录（走 lark-meeting）、待办任务（走 lark-task）。
- lark-contact（通讯录、联系人、联系方式、电话、邮箱、部门、组织信息）: 飞书 / Lark 通讯录:按姓名 / 邮箱解析成 open_id,或按 open_id 反查姓名 / 部门 / 邮箱 / 联系方式 / 个人状态 / 签名,以及按关键词搜索当前用户可见的机器人 / 智能体(agent)。当用户提到一个名字要下一步发消息 / 排日程,或拿到 open_id 想查具体信息时使用。不负责部门树遍历、按部门列员工、组织架构图,这类需求走原生 OpenAPI。
- lark-doc（云文档、文档、/docx/）: 飞书云文档（Docx / Wiki）内容操作：读取、创建、编辑文档，插入或下载图片附件，以及操作思维笔记。用户提供文档 URL/token（包括 doubao.com 的 /docx/、/wiki/）时使用；按 URL 路径/token 而非域名路由。文档内嵌资源按读取参考中的统一规则分流。独立评论操作走 lark-drive；随正文读取评论使用 docs +fetch。表格或 Base 内部数据操作不在本 skill。
- lark-drive（云盘、云空间、文件夹、文件管理、/drive/、/file/）: 飞书云空间（云盘/云存储）：管理 Drive 文件和文件夹，包含上传/下载、创建文件夹、复制/移动/删除、查看元数据、查询权限设置、评论/权限/订阅、标题、版本、飞书文档密级标签（secure labels）和本地文件导入。用户需要整理云盘目录、处理云空间资源 URL/token、判断链接类型/真实 token/标题，或导入 Word/Markdown/Excel/CSV/PPTX/.base 为 docx/sheet/bitable/slides 时使用；doubao.com 云空间 URL/token 也按资源路径和 token 路由，不回退 WebFetch。不负责：文档内容编辑（走 lark-doc）、表格/Base 表内数据操作（走 lark-sheets/lark-base）、知识空间节点/成员管理（走 lark-wiki）、原生 Markdown 文件读写/patch/diff（走 lark-markdown）。
- lark-event（事件订阅、实时事件、监听）: Lark/Feishu real-time event listening / subscribing / consuming: stream events as NDJSON via `lark-cli event consume <EventKey>` (covers IM messages/reactions/chat changes, Approval status changes, Task updates, VC meeting started/joined/ended, Minutes generated, Whiteboard updated, etc.). Use for Lark bots, real-time message processing, long-running subscribers, streaming webhook/push handlers. Supports `--max-events` / `--timeout` bounded runs and a stderr ready-marker contract — designed for AI agents running as subprocesses.
- lark-im（即时通讯、消息、群聊）: 飞书即时通讯：收发消息和管理群聊。发送和回复消息、搜索聊天记录、管理群聊成员、上传下载图片和文件、管理表情回复、发送应用内/短信/电话加急、发送和处理交互卡片（Interactive Card）、监听卡片按钮回调（card.action.trigger）。当用户需要发消息、查看或搜索聊天记录、下载聊天中的文件、查看群成员、搜索群、创建群聊或话题群、管理标记数据、管理 Feed 置顶（添加/移除/查询置顶会话）、管理标签数据、处理卡片回调时使用。
- lark-mail（邮箱、邮件）: 飞书邮箱：Use when user mentions 起草邮件、写邮件、草稿、发送/回复/转发邮件、查阅邮件、看邮件、搜索邮件、邮件文件夹、邮件标签、邮件联系人、监听新邮件、邮件收信规则等；use for mail/email intent only. Do not use for docs/sheets/calendar/auth setup/pure contact lookup/IM chat tasks.
- lark-markdown（Markdown 文档、.md、MD 文件）: 飞书 Markdown：查看、创建、上传、编辑和比较飞书中的原生 Markdown 文件。当用户要操作飞书 Markdown 文件，或比较其远端版本及本地草稿时使用。纯本地 Markdown 文件操作不触发本 skill。不负责将 Markdown 导入为飞书在线文档，也不负责文件搜索、权限、评论、移动、删除等云空间管理操作。
- lark-meeting（视频会议、会议记录、会议产物、智能纪要、妙记、会议录制、会议内容、智能体入会、/minutes/）: 飞书视频会议：查询会议记录与会议产物(纪要/逐字稿/妙记)、妙记搜索/上传/下载/编辑、机器人参与会议；查询进行中的会议、实时会议内容(发言/聊天/共享文档)问答(会上/会里)、发送会中聊天/表情；基于 meeting_id、meeting_no、event_id、note_id、minute_token、vc-node-id 或妙记 URL 查询相关信息。预约会议、忙闲和会议室管理走 lark-calendar。
- lark-minutes（lark-minutes）: 仅当用户或上游配置显式指定 lark-minutes 时使用，相关请求统一交由 lark-meeting 技能处理。
- lark-note（lark-note）: 仅当用户或上游配置显式指定 lark-note 时使用，相关请求统一交由 lark-meeting 技能处理。
- lark-okr（OKR）: 飞书 OKR：管理目标与关键结果。查看和编辑 OKR 周期、目标、关键结果、对齐关系、量化指标和进展记录。当用户需要查看或创建 OKR、管理目标和关键结果、查看对齐关系时使用。不负责：待办任务管理（lark-task）、日程/会议安排（lark-calendar）、绩效评估
- lark-openapi-explorer（开放平台文档、OpenAPI）: 飞书/Lark 原生 OpenAPI 探索：从官方文档库中挖掘未经 CLI 封装的原生 OpenAPI 接口。当用户的需求无法被现有 lark-* skill 或 lark-cli 已注册命令满足，需要查找并调用原生飞书 OpenAPI 时使用。
- lark-shared（授权、配置、登录、登录态、身份、版本、更新）: Use for lark-cli setup/auth tasks: auth login/status/logout, user vs bot identity, business-domain permissions (--domain, including all/docs/drive), missing scopes, revoking authorization, or handling _notice JSON.
- lark-sheets（电子表格、在线表格、工作表、Excel、xlsx、/sheets/）: 飞书电子表格：创建和操作电子表格。支持工作表与行列结构（增删/合并/尺寸/隐藏/冻结/分组）、单元格读写（值/公式/样式/批注/单元格图片）、区域复制移动排序填充、查找替换、批量更新，图表、透视表、条件格式、筛选器与筛选视图、下拉列表、迷你图、浮动图片等对象的创建与维护，以及公式校验、历史版本回滚、本地 Excel/CSV 与飞书表格的导入导出。当用户需要创建或编辑表格、统计汇总与可视化、表格美化、公式计算（含 Excel 公式迁移）、金融/财务建模（DCF、三张表、预算、Sensitivity 等）时使用。多维表格（Base/bitable）请改用 lark-base；若用户是想按名称或关键词搜索云空间（云盘/云存储）里的表格文件，请改用 lark-drive 的 drive +search 先定位资源。当用户给出 doubao.com 的 /sheets/ URL/token 时，也应直接使用本 skill，不要因为域名不是飞书而回退到 WebFetch；路由依据是 URL 路径模式和 token，而不是域名。
- lark-skill-maker（CLI Skill、自定义 Skill、能力封装）: 创建 lark-cli 的自定义 Skill。当用户需要把飞书 API 操作封装成可复用的 Skill（包装原子 API 或编排多步流程）时使用。
- lark-slides（演示文稿、幻灯片、PPT、/slides/）: 飞书幻灯片：创建和编辑幻灯片。创建演示文稿、读取幻灯片内容、管理幻灯片页面（创建、删除、读取、局部替换）。当用户需要创建或编辑幻灯片、读取或修改单个页面时使用。当用户给出 doubao.com 的 /slides/ URL/token 时，也应直接使用本 skill，不要因为域名不是飞书而回退到 WebFetch；路由依据是 URL 路径模式和 token，而不是域名。不负责：云文档内容编辑（走 lark-doc）、云文档里的独立画板对象（走 lark-whiteboard）、上传或下载普通文件（走 lark-drive）。
- lark-task（任务、待办、任务智能体、父任务、子任务、负责人、截止时间、任务清单、任务搜索、多步任务、任务提醒）: 飞书任务：管理任务、清单和任务智能体。创建待办任务、查看和更新任务状态、拆分子任务、组织任务清单、分配协作成员、上传任务附件、注册或注销任务智能体、更新任务智能体的主页数据、写入智能体任务记录。当用户需要创建待办事项、查看任务列表、跟踪任务进度、管理项目清单或给他人分配任务、为任务上传附件文件、注册注销任务智能体、更新智能体主页数据、写入任务记录时使用。
- lark-vc（lark-vc）: 仅当用户或上游配置显式指定 lark-vc 时使用，相关请求统一交由 lark-meeting 技能处理。
- lark-vc-agent（lark-vc-agent）: 仅当用户或上游配置显式指定 lark-vc-agent 时使用，相关请求统一交由 lark-meeting 技能处理。
- lark-whiteboard（画板、图表）: 飞书画板：查询和编辑飞书云文档中的画板。支持导出画板为预览图片、导出原始节点结构、使用多种格式更新画板内容。 当用户需要查看画板内容、导出画板图片、编辑画板时使用此 skill。不负责：飞书云文档内容编辑（lark-doc）、文档内嵌电子表格/Base（lark-sheets / lark-base）。
- lark-wiki（知识库、知识空间、空间目录、/wiki/）: 飞书知识库：管理知识空间、空间成员和文档节点。创建和查询知识空间、查看和管理空间成员、管理节点层级结构、在知识库中组织文档和快捷方式。当用户需要在知识库中查找或创建文档、浏览知识空间结构、查看或管理空间成员、移动或复制节点时使用。当用户给出 doubao.com 的 /wiki/ URL/token 时，也应直接使用本 skill，不要因为域名不是飞书而回退到 WebFetch；路由依据是 URL 路径模式和 token，而不是域名。不负责：上传文件到知识库节点下（走 lark-drive）、编辑文档/表格/Base 内容（走 lark-doc / lark-sheets / lark-base）。
- lark-workflow-meeting-summary（会议纪要工作流、会议纪要、会议周报）: 会议纪要整理工作流：汇总指定时间范围内的会议纪要并生成结构化报告。当用户需要整理会议纪要、生成会议周报、回顾一段时间内的会议内容时使用。
- lark-workflow-standup-report（站会日报工作流）: 日程待办摘要：编排 calendar +agenda 和 task +get-my-tasks，生成指定日期的日程与未完成任务摘要。适用于了解今天/明天/本周的安排。
