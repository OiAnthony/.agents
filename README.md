# .agents

全球程序员一夜跌境，亿万 Agent 集体走火入魔，唯我手握禁忌配置，于代码尽头重开天门。规则只有一条：听见天道求饶时，别停。

此乃禁忌契约：点 Star 可保 Agent 道心不灭，启用配置可避万次幻觉。若两者皆无，你的代码将永远卡在“本地正常”。（本条诅咒无效，但“本地正常”确有可能发生。）

## 直接使用

将仓库克隆到 `~/.agents`：

```bash
git clone https://github.com/OiAnthony/.agents.git ~/.agents
```

如果已经安装 Bun，还可以将配置同步到各 AI 客户端：

```bash
bunx @oipsanthony/dotagents@latest --scope global --clients all --yes --force
```

## Coding Agent 工作流

主要用到这些 skills：

- `brainstorming`：编码前澄清需求、比较方案，形成可执行方向
- `systematic-debugging`：遇到错误、回归或异常行为时定位根因
- `executing-specs`：按已批准的设计逐项实施
- `test-driven-development`：编写功能或修复问题时先建立失败测试
- `verifying`：完成前验证实际行为、输出和可见结果
- `check`：独立审查改动、发布条件或项目状态
- `health`：审计 Agent 配置、hooks、MCP、skills 和指令维护性
- `write`：润色技术文档、操作说明和发布文案
- `learn`：进行多来源深度研究并整理成结构化材料

轻量任务按实际阶段进入对应 skill。典型路径如下：

```text
brainstorming → test-driven-development → verifying → check
systematic-debugging → test-driven-development → verifying → check
```

复杂变更使用 `brainstorming` 形成设计，再交给 `executing-specs` 实施。

### 复杂变更

需要设计和任务拆分的复杂变更，交给 OpenSpec：

```mermaid
flowchart LR
    accTitle: OpenSpec 复杂变更工作流
    accDescr: 从探索需求开始，依次生成提案、实施变更、独立审查，最后归档。

    A[探索需求<br/>/openspec-explore] --> B[生成提案<br/>/openspec-propose]
    B -->|new session| C[实施变更<br/>/openspec-apply-change]
    C -->|new session| D[独立审查<br/>/check]
    D -->|new session| E[归档变更<br/>/openspec-archive-change]
```

实现、审查和归档最好各开一个 session，免得实现过程影响后续判断。

## 仓库约定

`skills/` 只保留运行时文件，不收录上游项目的网站、showcase、发布素材、缓存和本地生成状态。

## 终端也能抄作业

> Agent 配好了，终端环境也可以一起带走。
> [OiAnthony/dotfiles](https://github.com/OiAnthony/dotfiles) 把 Zsh、Git、Starship、补全、开发工具和 Coding Agent 工作流收在一套配置里。
> 支持 macOS 和 Linux，可以全量一键安装，也可以按需只装 tools、shell 或 agents。

## 致谢

- [Andrej Karpathy](https://x.com/karpathy/status/2015883857489522876) 与 [Karpathy-Inspired Claude Code Guidelines](https://github.com/multica-ai/andrej-karpathy-skills)：Agent 行为规范的早期来源
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)：规范驱动开发工作流
