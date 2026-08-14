# Logging Techniques for Debugging

Every log answers a yes/no question about a hypothesis: "if this prints X before Y, hypothesis A holds; otherwise A is dead." A log that cannot rule a hypothesis in or out is noise.

## Discriminating Content

Log what discriminates between hypotheses: ordering (sequence number or timestamp), input identity key, branch taken, old-vs-new state transition, and error code plus context. Place logs at boundaries where behavior should be predictable (handler entry/exit, cache hit or miss with key, state setter with old value and caller, async callback entry, external API result) rather than in tight-loop interiors. Never log credentials, PII, or full request/response bodies.

For race conditions, flicker, or intermittent failures, also capture event identity, monotonic ordering, start and end (not just "it ran"), and thread/task/queue identity. If adding a log changes the behavior, that is evidence of a timing, lifecycle, or concurrency problem, not "logging side effects" to dismiss.

## Runner-Only Failures

When a script fails only under a specific runner (make target, CI job, test harness, cron) but passes standalone, do not edit the script with debug hacks you might forget to remove. Inject tracing from the outside via the environment the runner already passes through:

```bash
# xtrace-env.sh: sourced by every non-interactive bash via BASH_ENV
exec 19>>/path/to/persistent/xtrace.log
export BASH_XTRACEFD=19
export PS4='+ [$0:$LINENO] '
set -x
```

Run the failing pipeline as `BASH_ENV=/path/to/xtrace-env.sh make test` (or the runner's equivalent). Every bash the runner spawns appends `file:line`-stamped traces to one persistent file, surviving the runner's temp-dir cleanup, so the exact dying line is on record even when the failure needs the full pipeline to reproduce. Guard the injection with a sentinel variable if nested shells would re-source it, and delete the env file when done.
