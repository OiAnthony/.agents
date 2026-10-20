"""Synthetic regression coverage for conversation audit OMP telemetry."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("conversation_audit.py")
SPEC = importlib.util.spec_from_file_location("conversation_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class OmpTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / "workspace"
        self.project.mkdir()
        self.root = self.base / "sessions"
        self.root.mkdir()
        self.project_sessions = self.root.resolve() / ("-" + str(self.project).lstrip("/").replace("/", "-"))
        self.project_sessions.mkdir()
        self.parent = self.project_sessions / "parent.jsonl"
        self.old_time = 1_700_000_000

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_records(self, path: Path, records: list[dict[str, object]], *, old: bool = True) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        if old:
            os.utime(path, (self.old_time, self.old_time))

    def header(self, session_id: str, cwd: Path | None = None) -> dict[str, object]:
        return {"type": "session", "id": session_id, "timestamp": "2026-01-01T00:00:00Z", "cwd": str(cwd or self.project)}

    def output(self) -> str:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            AUDIT.print_omp_receipts(self.root, self.project, "deep")
        return stream.getvalue()

    def test_duplicate_event_and_incomplete_call_are_reported(self) -> None:
        tool_call = {"type": "message", "id": "message-1", "timestamp": "2026-01-01T00:00:01Z", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "call-1", "name": "read", "arguments": {"path": "private"}}]}}
        self.write_records(self.parent, [self.header("parent"), tool_call, tool_call])
        output = self.output()
        self.assertIn("omp_duplicate_events: 1", output)
        self.assertIn("omp_tool_calls_linked: 1", output)
        self.assertIn("omp_incomplete_tool_calls: 1", output)
        self.assertNotIn("private", output)

    def test_missing_timing_is_not_inferred(self) -> None:
        call = {"type": "message", "id": "m1", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": "c1", "name": "shell", "arguments": {"command": "secret"}}]}}
        result = {"type": "message", "id": "m2", "timestamp": "2026-01-01T00:00:02Z", "message": {"role": "toolResult", "toolCallId": "c1", "isError": False, "content": "ok"}}
        self.write_records(self.parent, [self.header("parent"), call, result])
        output = self.output()
        self.assertIn("omp_tool_results_linked: 1", output)
        self.assertIn("omp_missing_tool_starts: 1", output)
        self.assertIn("omp_timing_gaps: 1", output)
        self.assertIn("omp_tool_interval_samples: 0", output)
        self.assertIn("omp_coverage_status: partial", output)
        self.assertNotIn("secret", output)

    def test_parent_worker_discovery_and_unrelated_project_exclusion(self) -> None:
        parent_id = "parent"
        child_dir = self.project_sessions / "parent"
        worker = child_dir / "worker.jsonl"
        parent_records = [self.header(parent_id), {"type": "custom", "customType": "vibe-session-lifecycle", "id": "spawn", "data": {"action": "spawn", "childSessionFile": str(worker), "parentSessionId": parent_id}}]
        self.write_records(self.parent, parent_records)
        self.write_records(worker, [self.header("child")])
        other_project = self.base / "other"
        other_project.mkdir()
        other_root = self.root / ("-" + str(other_project).lstrip("/").replace("/", "-"))
        other_root.mkdir()
        other_file = other_root / "unrelated.jsonl"
        self.write_records(other_file, [self.header("other", other_project)])
        files, gap = AUDIT.discover_omp_files(self.root, self.project)
        self.assertFalse(gap)
        self.assertEqual({self.parent, worker}, set(files))
        output = self.output()
        self.assertIn("omp_sessions_scanned: 2", output)
        self.assertNotIn("unrelated", output)

    def test_live_and_malformed_logs_are_coverage_gaps(self) -> None:
        self.write_records(self.parent, [self.header("parent")], old=False)
        output = self.output()
        self.assertIn("omp_live_files_skipped: 1", output)
        self.assertNotIn("omp_coverage_status: complete", output)
        self.parent.write_text(json.dumps(self.header("parent")) + "\n{broken\n", encoding="utf-8")
        os.utime(self.parent, (self.old_time, self.old_time))
        output = self.output()
        self.assertIn("omp_parse_errors: 1", output)
        self.assertIn("omp_coverage_status: partial", output)

    def test_file_changed_during_scan_is_reported_as_gap(self) -> None:
        self.write_records(self.parent, [self.header("parent")])
        original_open = Path.open
        opens = 0

        class AppendAfterRead:
            def __init__(self, handle, path):
                self.handle = handle
                self.path = path
            def __enter__(self):
                self.handle.__enter__()
                return self

            def __exit__(self, *args):
                result = self.handle.__exit__(*args)
                with original_open(self.path, "a", encoding="utf-8") as writer:
                    writer.write(json.dumps({"type": "custom", "id": "late"}) + "\n")
                return result

            def __iter__(self):
                return iter(self.handle)
            def readline(self, size=-1):
                return self.handle.readline(size)

        def intercepted_open(path, *args, **kwargs):
            nonlocal opens
            handle = original_open(path, *args, **kwargs)
            if path == self.parent:
                opens += 1
                if opens == 2:
                    return AppendAfterRead(handle, path)
            return handle

        from unittest.mock import patch

        with patch.object(Path, "open", autospec=True, side_effect=intercepted_open):
            output = self.output()
        self.assertIn("omp_changed_files: 1", output)
        self.assertIn("omp_coverage_status: partial", output)

    def test_timing_error_fingerprints_and_unknown_outcomes_are_separate(self) -> None:
        assistant = {"type": "message", "id": "a1", "timestamp": "2026-01-01T00:00:00Z", "message": {"role": "assistant", "duration": 120.0, "ttft": 30.0, "content": [{"type": "toolCall", "id": "c1", "name": "shell", "arguments": {"command": "hidden"}}, {"type": "toolCall", "id": "c2", "name": "shell", "arguments": {"command": "hidden"}}]}}
        start1 = {"type": "custom", "customType": "tool_execution_start", "id": "s1", "timestamp": "2026-01-01T00:00:01Z", "data": {"toolCallId": "c1", "startedAt": "2026-01-01T00:00:01Z"}}
        start2 = {"type": "custom", "customType": "tool_execution_start", "id": "s2", "timestamp": "2026-01-01T00:00:02Z", "data": {"toolCallId": "c2", "startedAt": "2026-01-01T00:00:02Z"}}
        result1 = {"type": "message", "id": "r1", "timestamp": "2026-01-01T00:00:03Z", "message": {"role": "toolResult", "toolCallId": "c1", "toolName": "shell", "isError": True, "content": "unknown failure 123"}}
        result2 = {"type": "message", "id": "r2", "timestamp": "2026-01-01T00:00:04Z", "message": {"role": "toolResult", "toolCallId": "c2", "toolName": "shell", "isError": True, "content": "unknown failure 456"}}
        self.write_records(self.parent, [self.header("parent"), assistant, start1, start2, result1, result2])
        output = self.output()
        self.assertIn("omp_tool_interval_samples: 2", output)
        self.assertIn("omp_assistant_duration_p50_ms: 120.0", output)
        self.assertIn("omp_assistant_ttft_p50_ms: 30.0", output)
        self.assertIn("omp_unknown_error_results: 2", output)
        self.assertIn("omp_tool_error_fingerprints: 1", output)
        self.assertIn("omp_repeated_error_events: 1", output)
        self.assertNotIn("harness_fault", output)
        self.assertNotIn("hidden", output)

    def test_millisecond_results_outcomes_waits_and_first_product_change(self) -> None:
        records = [self.header("parent")]
        base = 1767225600.0
        call_no = 0

        def add_call(call_id: str, offset: float, name: str, arguments: dict[str, object]) -> None:
            nonlocal call_no
            call_no += 1
            records.append({"type": "message", "id": f"call-event-{call_no}", "timestamp": AUDIT.datetime.fromtimestamp(base + offset, AUDIT.datetime.now().astimezone().tzinfo).isoformat(), "message": {"role": "assistant", "content": [{"type": "toolCall", "id": call_id, "name": name, "arguments": arguments}]}})

        def add_result(call_id: str, offset: float, *, error: bool = False, details: dict[str, object] | None = None, content: str = "ok", message_timestamp: object | None = None, outer_timestamp: str | None = None, event_id: str | None = None) -> None:
            records.append({"type": "message", "id": event_id or f"result-{call_id}", "timestamp": outer_timestamp or "2026-01-01T00:00:00Z", "message": {"role": "toolResult", "timestamp": message_timestamp if message_timestamp is not None else int((base + offset) * 1000), "toolCallId": call_id, "toolName": "bash", "isError": error, "details": details or {}, "content": content}})

        add_call("service", 0, "bash", {"command": "run service", "ready": {"port": 9000}})
        add_result("service", 0.2)
        add_call("wait-service", 0.3, "wait", {"i": "wait"})
        add_result("wait-service", 0.4)
        add_call("wait-finite", 0.5, "wait", {"i": "wait", "timeout": 10})
        add_result("wait-finite", 0.6)
        add_call("read", 0.7, "read", {"path": "src/app.ts"})
        add_result("read", 0.8)
        add_call("edit", 1.0, "edit", {"path": str(self.project / "src/app.ts"), "input": "private change"})
        records.append({"type": "custom", "customType": "tool_execution_start", "id": "start-edit", "timestamp": "2026-01-01T00:00:01Z", "data": {"toolCallId": "edit", "startedAt": "2026-01-01T00:00:01Z"}})
        add_result("edit", 2.0, message_timestamp=int((base + 2.0) * 1000), outer_timestamp="2026-01-01T00:00:02Z")
        add_call("fallback", 2.05, "bash", {"command": "ordinary command"})
        records.append({"type": "custom", "customType": "tool_execution_start", "id": "start-fallback", "timestamp": "2026-01-01T00:00:02Z", "data": {"toolCallId": "fallback", "startedAt": "2026-01-01T00:00:02Z"}})
        add_result("fallback", 2.15, message_timestamp="not-a-timestamp", outer_timestamp="2026-01-01T00:00:02.150Z")
        add_result("edit", 2.1, event_id="duplicate-edit-result")
        add_call("service-start", 2.1, "service_start", {})
        add_result("service-start", 2.15)
        add_call("wait-service-2", 2.16, "wait", {"i": "wait"})
        add_result("wait-service-2", 2.17)
        add_call("reject", 2.2, "bash", {"command": "invalid tool parameters"})
        add_result("reject", 2.3, error=True, content="Service mode does not accept async")
        add_call("validation-reject", 2.31, "edit", {"path": "src/app.ts", "input": "invalid"})
        add_result("validation-reject", 2.32, error=True, content="Validation failed: missing argument")
        add_call("toolerror-reject", 2.33, "write", {"path": "src/app.ts", "content": "invalid"})
        add_result("toolerror-reject", 2.34, error=True, content="ToolError: invalid parameter")
        add_call("exec-fail", 2.4, "bash", {"command": "run command"})
        add_result("exec-fail", 2.5, error=True, details={"exitCode": 1}, content="command failed")
        add_call("test-fail", 2.6, "bash", {"command": "pytest tests"})
        add_result("test-fail", 2.7, error=True, details={"exitCode": 1}, content="tests failed")
        add_call("expected", 2.8, "bash", {"command": "run check"})
        add_result("expected", 2.9, error=True, content="expected failure")
        add_call("timeout", 3.0, "bash", {"command": "run slow"})
        add_result("timeout", 3.1, error=True, details={"timedOut": True}, content="stopped")
        self.write_records(self.parent, records)

        output = self.output()
        self.assertIn("omp_tool_interval_samples: 2", output)
        self.assertIn("omp_tool_interval_p50_ms: 575.0", output)
        self.assertIn("omp_duplicate_tool_results: 1", output)
        self.assertIn("omp_rejected_parameter_results: 3", output)
        self.assertIn("omp_execution_failure_results: 1", output)
        self.assertIn("omp_test_failure_results: 1", output)
        self.assertIn("omp_expected_negative_results: 1", output)
        self.assertIn("omp_timeout_results: 1", output)
        self.assertIn("omp_service_only_waits: 2", output)
        self.assertIn("omp_finite_waits: 1", output)
        self.assertIn("omp_calls_before_first_successful_product_modification: 4", output)
        self.assertNotIn("private change", output)

    def test_existing_claude_and_codex_message_parsing_remains_available(self) -> None:
        claude = AUDIT.message_from_record({"type": "user", "message": {"role": "user", "content": "please fix this"}}, 1)
        codex = AUDIT.message_from_record({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "done"}]}}, 2)
        self.assertEqual(("user", "please fix this"), (claude.role, claude.text))
        self.assertEqual(("assistant", "done"), (codex.role, codex.text))


if __name__ == "__main__":
    unittest.main()
