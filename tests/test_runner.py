from pathlib import Path

from jobs.runner import build_status_panel, run_job
from jobs.state import JobStage


def test_partial_extraction_recoverable(tmp_path):
    source = tmp_path / "x.pdf"
    source.write_bytes(b"x")
    state = run_job("job1", source, total_pages=3, extracted_pages=2)
    panel = build_status_panel(state)
    assert panel["errors"]
    assert any(e["code"] == "MULTIPAGE_PARTIAL_EXTRACTION" for e in panel["errors"])


def test_retry_from_stage_and_plugin_failure(tmp_path):
    source = tmp_path / "x.pdf"
    source.write_bytes(b"x")

    def broken_plugin():
        raise RuntimeError("plugin crashed")

    state = run_job(
        "job2",
        source,
        total_pages=1,
        extracted_pages=1,
        plugin=broken_plugin,
        retry_from_stage=JobStage.TRANSFORM,
    )
    assert any(e["code"] == "PLUGIN_FAILURE" for e in state.errors)
