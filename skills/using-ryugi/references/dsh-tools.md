# DeepSeek Harness (`dsh`) Tool Mapping

Skills speak in actions ("invoke a skill", "dispatch a subagent", "create a todo", "read a file"). On DeepSeek Harness (`dsh`) these resolve to the tools below.

| Action skills request                                        | DeepSeek Harness equivalent                                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Read a file                                                  | `read` (and `read_image` for images)                                                                   |
| Create a new file                                            | `write`                                                                                                |
| Edit a file                                                  | `edit` (or `apply_patch` for multi-hunk patches)                                                       |
| Run a shell command                                          | `bash` (or `pwsh` on Windows; manage background jobs with `job_list`, `job_output`, `job_kill`)        |
| Search file contents                                         | `grep`                                                                                                 |
| Find files by path or pattern                                | `glob`                                                                                                 |
| Fetch a URL                                                  | `web_fetch`                                                                                            |
| Search the web                                               | `web_search`                                                                                           |
| Ask your human partner a structured question                 | `ask_user_question`                                                                                    |
| Invoke a skill (`Skill` tool)                                | DSH's native `skill` tool using kebab-case `ryugi-<name>` (replace `:` with `-`, e.g. `ryugi:brainstorming` → `ryugi-brainstorming`) |
| Create / update todos (`TodoWrite`)                          | `todo_write`                                                                                           |
| Dispatch a subagent (`Subagent (general-purpose):` template) | `subagent` (plus `subagent_fork`, `wait_agent`, `send_message`, `list_agents` for multi-agent work)    |

## Skills discovery and bootstrap

`dsh-plugin-ryugi` registers a Cordis `skills` provider that exposes every skill under `skills/` as `ryugi-<name>` (kebab-case, since DSH forbids `:` in skill names) to DSH's native `skill` tool without copying files. On `agent/pre-step`, it injects `using-ryugi` + this tool mapping once as a user-role message for top-level sessions, deduplicating against `session.deriveMessages()` so compaction automatically re-injects the bootstrap when older messages are summarized away.

## Live comment delivery

When a project has `.ryugi/artifacts/`, `dsh-plugin-ryugi` opens a Ryugi Hub channel for the active session and delivers browser comments, choice submissions, and document answers directly into the DSH session via `agent.followup` (when idle) or `agent.inject` (when running). Prefix every `ryugi.cjs` command with `AI_AGENT=dsh` and the session's `PI_SESSION_ID` printed in the bootstrap mapping: the session id subscribes the current DSH session, and `AI_AGENT=dsh` signs the replies and keeps the read state as DeepSeek Harness instead of Pi, the other agent on the same channel.
