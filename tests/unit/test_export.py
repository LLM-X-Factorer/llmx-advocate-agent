"""Unit tests for core/export.py — bundle construction + disk persistence.

Coverage:
- build_export_bundle for a fully-completed task with all 9 phases passed
- build_export_bundle for partial completion (only P1/P2 passed)
- source_pack_id extraction from P1's SourcePack output
- build_failure_bundle for a task that hit qa_failed_terminal
- build_failure_bundle when error info lives in output._error / _traceback
- persist_to_disk writes correct file tree for COMPLETED
- persist_to_disk writes failures/ subtree for FAILED
- persist_to_disk returns None for non-terminal status
- atomic write — partial files don't appear under final names
- source-pack.md only written when task.source.pack_content is set
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from llmx_advocate.core.export import (
    build_export_bundle,
    build_failure_bundle,
    persist_to_disk,
)
from llmx_advocate.core.models import (
    PhaseId,
    PhaseRun,
    PhaseRunStatus,
    QAGate,
    QAResult,
    SourceInput,
    Task,
    TaskConfig,
    TaskStatus,
)


def _make_task(status: TaskStatus = TaskStatus.COMPLETED, with_pack_content: bool = True) -> Task:
    now = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    return Task(
        id="01TESTTASK0001",
        title="Test task",
        source=SourceInput(
            pack_path=None,
            pack_content="---\npack_id: pack-001\n---\nbody" if with_pack_content else None,
        ),
        config=TaskConfig(llm_provider="openrouter", llm_model="deepseek/deepseek-chat"),
        current_phase=PhaseId.P6,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _passed_run(phase: PhaseId, output: dict, attempt: int = 1) -> PhaseRun:
    now = datetime(2026, 4, 27, 10, 5, 0, tzinfo=UTC)
    return PhaseRun(
        id=f"run-{phase}-{attempt}",
        task_id="01TESTTASK0001",
        phase_id=phase,
        attempt=attempt,
        trigger="auto",
        llm_provider="openrouter",
        llm_model="deepseek/deepseek-chat",
        output=output,
        qa_result=QAResult(gates=[QAGate(gate_id="t", name="t", passed=True, rationale="ok")], passed_overall=True),
        status=PhaseRunStatus.PASSED,
        started_at=now,
        finished_at=now,
        duration_ms=100,
    )


def _full_run_set() -> list[PhaseRun]:
    return [
        _passed_run(PhaseId.P1, {"pack_id": "pack-001", "body_markdown": "..."}),
        _passed_run(PhaseId.P1_5, {"hook_source": "..."}),
        _passed_run(PhaseId.P2, {"tier": "留存", "characteristic_scores": {}}),
        _passed_run(PhaseId.P2_5, {"full_sentence": "表面看是 X，实则是 Y。"}),
        _passed_run(PhaseId.P2_6, {"theme": "稀疏模型的红利在内存墙上被讨价还价"}),
        _passed_run(PhaseId.P3, {"findings": []}),
        _passed_run(PhaseId.P4, {"export_formats": ["landscape"], "scenes": [{"scene_type": "cover"}]}),
        _passed_run(PhaseId.P5, {"syntax_ok": True}),
        _passed_run(PhaseId.P6, {"titles": [{"text": "标题 A", "formula_id": "T-3", "rationale": "决策者口味"}], "description": "🎯", "pinned_comment": "00:00"}),
    ]


def test_build_export_bundle_full():
    task = _make_task()
    bundle = build_export_bundle(task, _full_run_set())
    assert bundle.task_id == "01TESTTASK0001"
    assert bundle.status == "completed"
    assert bundle.source_pack_id == "pack-001"
    assert bundle.judgment == "表面看是 X，实则是 Y。"
    assert bundle.theme == "稀疏模型的红利在内存墙上被讨价还价"
    assert bundle.tier == "Tier.LIUCUN" or bundle.tier == "留存"  # Tier enum stringified
    assert bundle.video_json is not None
    assert bundle.publishing is not None


def test_build_export_bundle_partial():
    """Only P1 and P2 passed — bundle should still construct, with None for missing."""
    task = _make_task(status=TaskStatus.PAUSED_FOR_HUMAN)
    runs = [
        _passed_run(PhaseId.P1, {"pack_id": "pack-002"}),
        _passed_run(PhaseId.P2, {"tier": "引流"}),
    ]
    bundle = build_export_bundle(task, runs)
    assert bundle.source_pack_id == "pack-002"
    assert bundle.video_json is None
    assert bundle.publishing is None
    assert bundle.judgment is None
    assert bundle.theme is None


def test_build_export_bundle_no_p1():
    """No P1 passed — source_pack_id is None, but we don't crash."""
    task = _make_task()
    bundle = build_export_bundle(task, [])
    assert bundle.source_pack_id is None
    assert bundle.judgment is None


def test_to_api_dict_matches_legacy_shape():
    """Refactor invariant: to_api_dict() must match the previous TaskExport shape."""
    task = _make_task()
    bundle = build_export_bundle(task, _full_run_set())
    api = bundle.to_api_dict()
    assert set(api.keys()) == {"task_id", "title", "status", "video_json", "publishing", "judgment", "theme", "tier"}


def test_to_summary_markdown_includes_key_fields():
    task = _make_task()
    bundle = build_export_bundle(task, _full_run_set())
    md = bundle.to_summary_markdown()
    assert bundle.title in md
    assert bundle.task_id in md
    assert "## Theme" in md
    assert "## Core Judgment" in md
    assert "## Title Options" in md
    assert "标题 A" in md
    assert "[T-3]" in md


def test_build_failure_bundle_with_error_in_output():
    task = _make_task(status=TaskStatus.FAILED)
    now = datetime(2026, 4, 27, 10, 5, 0, tzinfo=UTC)
    runs = [
        _passed_run(PhaseId.P1, {"pack_id": "pack-fail-1"}),
        PhaseRun(
            id="run-p1.5-3",
            task_id=task.id,
            phase_id=PhaseId.P1_5,
            attempt=3,
            trigger="auto",
            llm_provider="openrouter",
            llm_model="deepseek/deepseek-chat",
            output={"_error": "JSONDecodeError: ...", "_traceback": "Traceback (most recent call last):\n..."},
            qa_result=None,
            status=PhaseRunStatus.ERROR,
            started_at=now,
            finished_at=now,
            duration_ms=500,
        ),
    ]
    failure = build_failure_bundle(task, runs)
    assert failure.failed_phase == "P1.5"
    assert failure.failed_attempts == 3
    assert "JSONDecodeError" in failure.last_error
    assert failure.last_traceback is not None
    assert failure.source_pack_id == "pack-fail-1"


def test_build_failure_bundle_with_qa_failed_terminal():
    task = _make_task(status=TaskStatus.FAILED)
    now = datetime(2026, 4, 27, 10, 5, 0, tzinfo=UTC)
    runs = [
        _passed_run(PhaseId.P1, {"pack_id": "pack-fail-2"}),
        PhaseRun(
            id="run-p2.5-5",
            task_id=task.id,
            phase_id=PhaseId.P2_5,
            attempt=5,
            trigger="auto",
            llm_provider="openrouter",
            llm_model="deepseek/deepseek-chat",
            output={"full_sentence": "judgment"},
            qa_result=QAResult(
                gates=[
                    QAGate(gate_id="P2.5_uniqueness", name="独特性", passed=True, rationale="ok"),
                    QAGate(gate_id="P2.5_anti_relay_judge", name="反搬运", passed=False, rationale="judgment relies on source backing"),
                ],
                passed_overall=False,
            ),
            status=PhaseRunStatus.QA_FAILED_TERMINAL,
            started_at=now,
            finished_at=now,
            duration_ms=500,
        ),
    ]
    failure = build_failure_bundle(task, runs)
    assert failure.failed_phase == "P2.5"
    assert "P2.5_anti_relay_judge" in failure.last_error
    assert len(failure.qa_gates) == 2


def test_build_failure_bundle_no_runs():
    """Edge case: task is FAILED but no runs recorded (shouldn't happen but harmless)."""
    task = _make_task(status=TaskStatus.FAILED)
    failure = build_failure_bundle(task, [])
    assert failure.failed_phase == "(unknown)"
    assert failure.failed_attempts == 0


def test_persist_to_disk_completed(tmp_path):
    task = _make_task()
    runs = _full_run_set()
    written = persist_to_disk(task, runs, tmp_path)

    assert written is not None
    assert written == tmp_path / "2026-04-27" / task.id

    assert (written / "task.json").exists()
    assert (written / "summary.md").exists()
    assert (written / "video.json").exists()
    assert (written / "publishing.json").exists()
    assert (written / "source-pack.md").exists()

    task_meta = json.loads((written / "task.json").read_text())
    assert task_meta["task_id"] == task.id
    assert task_meta["source_pack_id"] == "pack-001"
    assert task_meta["status"] == "completed"


def test_persist_to_disk_failed(tmp_path):
    task = _make_task(status=TaskStatus.FAILED)
    now = datetime(2026, 4, 27, 10, 5, 0, tzinfo=UTC)
    runs = [
        PhaseRun(
            id="run-fail",
            task_id=task.id,
            phase_id=PhaseId.P2_5,
            attempt=5,
            trigger="auto",
            llm_provider="openrouter",
            llm_model="deepseek/deepseek-chat",
            output={"_error": "boom"},
            qa_result=None,
            status=PhaseRunStatus.ERROR,
            started_at=now,
            finished_at=now,
            duration_ms=500,
        ),
    ]
    written = persist_to_disk(task, runs, tmp_path)

    assert written is not None
    assert written == tmp_path / "failures" / "2026-04-27" / task.id
    assert (written / "task.json").exists()
    assert (written / "error.md").exists()
    err_md = (written / "error.md").read_text()
    assert "P2.5" in err_md
    assert "boom" in err_md


def test_persist_to_disk_skips_non_terminal_status(tmp_path):
    task = _make_task(status=TaskStatus.PAUSED_FOR_HUMAN)
    written = persist_to_disk(task, [], tmp_path)
    assert written is None
    # Nothing should have been created
    assert list(tmp_path.iterdir()) == []


def test_persist_to_disk_omits_source_pack_when_pack_path_only(tmp_path):
    task = _make_task(with_pack_content=False)
    written = persist_to_disk(task, _full_run_set(), tmp_path)
    assert written is not None
    assert not (written / "source-pack.md").exists()


def test_atomic_write_no_tmp_files_on_disk(tmp_path):
    task = _make_task()
    written = persist_to_disk(task, _full_run_set(), tmp_path)
    assert written is not None
    # No .tmp files should remain after a successful write
    leftover = list(written.glob("*.tmp"))
    assert leftover == []
