# OMP (Oh My Pi) Tool Mapping

Skills speak in actions ("invoke a skill", "dispatch a subagent", "create a todo", "read a file"). On OMP (`omp`) these resolve to the tools below.

| Action skills request                                        | OMP equivalent                                                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Read a file                                                  | `read`                                                                                                 |
| Create a new file                                            | `write`                                                                                                |
| Edit a file                                                  | `edit` (or `ast_edit` for structural AST edits)                                                        |
| Run a shell command                                          | `bash`                                                                                                 |
| Search file contents                                         | `grep` (or `ast_grep` for structural AST queries)                                                      |
| Find files by path or pattern                                | `glob` / `find`                                                                                        |
| Fetch a URL                                                  | `read` with the `http(s)://` URL (OMP has no separate `fetch` tool)                                    |
| Search the web                                               | `web_search`                                                                                           |
| Ask your human partner a structured question                 | `ask`                                                                                                  |
| Invoke a skill (`Skill` tool)                                | Call `read` with `skill://<name>` (or read the skill's `SKILL.md` directly — see [Loading skills](#loading-skills)) |
| Create / update todos (`TodoWrite`)                          | `todo`                                                                                                 |
| Dispatch a subagent (`Subagent (general-purpose):` template) | `task` (plus `wait` when awaiting background subagent completion)                                      |

## Loading skills

OMP discovers bundled Ryugi skills automatically, but does not expose a separate `Skill` tool. When a Ryugi workflow or instruction says to invoke a skill (for example `ryugi:brainstorming`, `ryugi:artifacts`, `ryugi:executing-specs`, `ryugi:test-driven-development`, `ryugi:systematic-debugging`, or `ryugi:verifying`), call `read` on `skill://<name>` (or read its `SKILL.md` path directly) and follow it. Using `read` is the sanctioned native skill-loading mechanism on OMP.

## Live comment delivery

The OMP Ryugi extension (`.omp/extensions/ryugi.ts`) spawns `ryugi-hook watch pi` on `session_start` and delivers browser comments, choice submissions, and document answers directly into the active OMP session via `sendMessage(..., { triggerTurn: true, deliverAs: 'followUp' })`.
