# Antigravity CLI (`agy`) Tool Mapping

Skills speak in actions ("invoke a skill", "dispatch a subagent", "create a todo", "read a file"). On the Antigravity CLI (`agy`) these resolve to the tools below.

| Action skills request                                        | Antigravity CLI equivalent                                                                                                                                                                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Read a file                                                  | `read_file` (or `view_file` in older Antigravity IDE environments)                                                                                                                                                                    |
| Create a new file                                            | `write_file` (or `write_to_file` in older Antigravity IDE environments)                                                                                                                                                               |
| Edit a file                                                  | `edit_file` (or `replace_file_content` / `multi_replace_file_content` in older Antigravity IDE environments)                                                                                                                          |
| Run a shell command                                          | `run_command` (try sandboxed first with `BypassSandbox: false`; pass `BypassSandbox: true` when a step requires network access or writing outside the workspace)                                                                      |
| Search file contents                                         | `grep_search`                                                                                                                                                                                                                         |
| Find files by name                                           | `find_by_name`                                                                                                                                                                                                                        |
| List files and subdirectories                                | `list_dir`                                                                                                                                                                                                                            |
| Fetch a URL                                                  | `read_url_content`                                                                                                                                                                                                                    |
| Search the web                                               | `search_web`                                                                                                                                                                                                                          |
| Ask your human partner a structured question                 | `ask_question` (for multiple-choice questions; ask trivial yes/no questions in plain text)                                                                                                                                            |
| Invoke a skill (`Skill` tool)                                | Read the skill's `SKILL.md` with `read_file` using the exact path listed in your `<skills>` prompt block (see [Loading skills](#loading-skills))                                                                                      |
| Dispatch a subagent (`Subagent (general-purpose):` template) | `invoke_subagent` with a built-in `TypeName` — `self` for full-capability work, `research` for read-only exploration (see [Subagent support](#subagent-support))                                                                      |
| Multiple parallel dispatches                                 | Multiple `invoke_subagent` calls (or `swarm` when coordinating a multi-agent board)                                                                                                                                                   |
| Task tracking ("create a todo", "mark complete")             | a **task artifact** — `write_file` / `edit_file` in the artifact directory with `ArtifactMetadata` (or `write_to_file` with `IsArtifact: true` and `ArtifactType: "task"`). **Not** `manage_task`, which manages background commands. |

## Loading skills

Antigravity discovers installed skills automatically and lists each skill's name, description, and `SKILL.md` path in your `<skills>` system prompt block, but does not expose a separate `Skill` tool. When a Ryugi workflow or instruction says to load or invoke a skill (for example `ryugi:brainstorming`, `ryugi:artifacts`, `ryugi:executing-specs`, `ryugi:test-driven-development`, `ryugi:systematic-debugging`, or `ryugi:verifying`), call `read_file` on that skill's `SKILL.md` path and follow it. Reading `SKILL.md` with `read_file` is the native skill-loading mechanism on Antigravity.

## Subagent support

Antigravity dispatches subagents via `invoke_subagent` (`TypeName`, `Role`, `Prompt`, optional `Workspace`). Built-in subagent types include:

- `self`: inherits your full toolset and configuration (use for implementation tasks or general-purpose subagent work).
- `research`: read-only sandbox for codebase exploration, verification, and builder/code review passes.
- `image-generator`: generates or edits images.

Fill all placeholders in a skill's prompt template before passing the complete prompt to `invoke_subagent`. Subagents run asynchronously and wake your turn automatically when they finish; do not poll them in a loop.

## Task tracking

Antigravity has **no todo tool** (`manage_task` manages background processes — `list`/`kill`/`status`/`send_input` — it is _not_ a checklist). When a skill says to create a todo list or track tasks, maintain a **task artifact**: a markdown checklist saved in the conversation's artifact directory (`<appDataDir>/brain/<conversation-id>/task.md`) using `write_file` with `ArtifactMetadata` (or `write_to_file` with `IsArtifact: true`, `ArtifactMetadata.ArtifactType: "task"`), and updated with `edit_file` (`replace_file_content` / `multi_replace_file_content`) as you go.

At the start of any multi-step task, create the task artifact listing every step of your plan. As you complete each step, edit the artifact to mark it done (`- [x]`). If the plan changes, update the checklist. Keep it current — it is your source of truth for what remains; once the conversation gets long, re-read it before starting each step.

## Artifacts sidecar pane

When the optional `ryugi/artifacts` plugin sidecar is enabled in Antigravity, you can link the local Ryugi Artifacts workbench inside Antigravity's Auxiliary Pane with `[Ryugi](sidecar://ryugi/artifacts/)`. Opening the pane lands on the conversation's most recent subscribed artifact automatically, follows new artifacts opened in that conversation, and falls back to a waiting screen until the local Ryugi server is running.
