# Exploratory work

Your human partner called the work exploratory: it stays uncommitted, in
place, until they keep it.

- Once `tasks.md` exists, write `<workspace>/EXPLORING`: first line
  `Exploratory: may be thrown away.`, then every path from the tasks'
  **Files:**, one per line. Add any path you touch later.
- No task commits. Close each task with
  `bash scripts/task-done SPEC_FILE N BASE --uncommitted -- <test command>`.
- Final review: `bash scripts/review-package SPEC_FILE --exploring`.
- Fixes for verify rejects stay uncommitted too, and their paths join
  `EXPLORING`.

**Finish.** Keep the workspace and `EXPLORING`. End your final message
with the listed paths and ask your human partner to keep it or discard it.

- Keep: commit the listed paths by name.
- Discard: `git restore` the listed paths that exist in HEAD and delete
  the listed files you created, nothing else.

Delete `EXPLORING` either way, then the workspace.
