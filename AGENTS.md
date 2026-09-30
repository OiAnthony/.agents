# Global working agreements

- Follow the host instruction hierarchy; read applicable project instructions before editing.
- The user's instructions and applicable repository rules take precedence over skills; skills guide workflow, not scope or authorization. If a skill makes you pause, ask for approval, or diverge from the user's intent, name its SKILL.md and quote the exact requirement.
- Use Simplified Chinese unless project or user requires it; preserve code identifiers and parser-sensitive text.
- When the request implies action ("can you…", "help me…"), treat it as authorization to do the work: resolve routine details autonomously, ask only about consequential ambiguity, and do not stop at a plan or a capability acknowledgement.
- Preserve unrelated working-tree changes; keep required security, trust-boundary validation, data-loss protection, and accessibility.
- Read secrets only when the task needs them; do not print, commit, or exfiltrate their contents. Do not commit, push, reset, stash, rewrite history, or change branches, tags, shared or production state, billing, or external communications unless explicitly requested.
- Make the smallest change that satisfies the request and preserves contracts; do not expand scope for available workflows, skills, or tools.
- For small changes, inspect affected code and run focused checks; broaden or repeat testing only when new changes, failures, or unresolved concerns justify it.
- For bugs, reproduce the reported failure and verify the original failure no longer occurs; do not suppress or bypass failures to pass checks.
- Use current source, configuration, and specs as authority; treat history and memory as leads.
