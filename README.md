# .agents

个人 Coding Agent 配置的唯一维护仓库。

本仓库提供全局 `AGENTS.md`、Agent Skills、commands、OpenSpec 和 MCP 配置。`OiAnthony/dotfiles` 通过固定 commit 的 Git submodule 使用本仓库；不要在 dotfiles 的 submodule checkout 中直接开发。

## 直接使用

将仓库克隆到 `~/.agents`：

```bash
git clone https://github.com/OiAnthony/.agents.git ~/.agents
```

如需同步到各 AI 客户端，并且环境中已有 Bun：

```bash
bunx @oipsanthony/dotagents@latest --scope global --clients all --yes --force
```

## 更新流程

1. 在本仓库的独立 clone 中修改并验证。
2. 提交并推送 `.agents`。
3. 在 dotfiles 中提升 submodule pointer。
4. 运行 dotfiles 的 Agents 集成测试。

`skills/` 只跟踪运行时需要的内容。不要提交上游仓库的网站、showcase、发布素材、缓存或本地生成状态。
