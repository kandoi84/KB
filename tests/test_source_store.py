import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.kb_runtime.source_store import record_source


ROOT = Path(__file__).resolve().parents[1]


def input_files(tmp_path, **changes):
    metadata = {
        "source_id": "SBI_Q1FY27",
        "entity": "SBI",
        "source_kind": "COMPANY_PRESENTATION",
        "url": "https://example.org/sbi-q1.pdf",
        "source_date": "2026-08-07",
        "observed_at": "2026-09-28T10:00:00+05:30",
        "retrieved_at": "2026-09-28T10:05:00+05:30",
    }
    metadata.update(changes)
    metadata_path = tmp_path / "input.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    raw_path = tmp_path / "source.pdf"
    raw_path.write_bytes(b"original filing bytes")
    return metadata_path, raw_path


def test_record_source_stores_raw_bytes_and_version_metadata(tmp_path):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"

    result = record_source(metadata_path, raw_path, project)

    raw_blob = project / "data/raw/sha256" / result["raw_sha256"]
    version = project / "data/registry/sources/SBI_Q1FY27" / f'{result["version_id"]}.json'
    assert raw_blob.read_bytes() == b"original filing bytes"
    record = json.loads(version.read_text(encoding="utf-8"))
    assert record["source_id"] == "SBI_Q1FY27"
    assert record["raw_sha256"] == result["raw_sha256"]
    assert record["version_id"] == result["version_id"]


def test_same_update_is_idempotent_and_changed_bytes_make_new_version(tmp_path):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"
    first = record_source(metadata_path, raw_path, project)
    assert record_source(metadata_path, raw_path, project) == first

    raw_path.write_bytes(b"revised filing bytes")
    second = record_source(metadata_path, raw_path, project)
    assert second["version_id"] != first["version_id"]
    assert (project / "data/raw/sha256" / first["raw_sha256"]).read_bytes() == b"original filing bytes"
    assert len(list((project / "data/registry/sources/SBI_Q1FY27").glob("*.json"))) == 2


@pytest.mark.parametrize("change", [
    {"entity": "HDFC Bank"},
    {"url": "https://example.org/other.pdf"},
    {"source_kind": "NEWS"},
])
def test_source_id_cannot_change_identity(tmp_path, change):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"
    record_source(metadata_path, raw_path, project)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(change)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="identity"):
        record_source(metadata_path, raw_path, project)
    assert len(list((project / "data/registry/sources/SBI_Q1FY27").glob("*.json"))) == 1


@pytest.mark.parametrize("change", [
    {"observed_at": "2026-09-28T10:00:00"},
    {"retrieved_at": "2026-09-28T10:05:00"},
    {"source_date": "not-a-date"},
    {"source_id": "../escape"},
])
def test_bad_metadata_cannot_be_recorded(tmp_path, change):
    metadata_path, raw_path = input_files(tmp_path, **change)
    project = tmp_path / "project"
    with pytest.raises(ValueError):
        record_source(metadata_path, raw_path, project)
    assert not (project / "data/registry").exists()


def test_existing_version_change_is_rejected(tmp_path):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"
    result = record_source(metadata_path, raw_path, project)
    version = project / "data/registry/sources/SBI_Q1FY27" / f'{result["version_id"]}.json'
    version.write_text('{"changed": true}', encoding="utf-8")

    with pytest.raises(ValueError, match="existing source version"):
        record_source(metadata_path, raw_path, project)


def test_older_version_tampering_blocks_later_update(tmp_path):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"
    first = record_source(metadata_path, raw_path, project)
    old_version = project / "data/registry/sources/SBI_Q1FY27" / f'{first["version_id"]}.json'
    record = json.loads(old_version.read_text(encoding="utf-8"))
    record["source_date"] = "2026-08-08"
    old_version.write_text(json.dumps(record), encoding="utf-8")
    raw_path.write_bytes(b"new filing bytes")

    with pytest.raises(ValueError, match="existing source version"):
        record_source(metadata_path, raw_path, project)
    assert len(list(old_version.parent.glob("*.json"))) == 1


def test_record_source_cli_reports_version(tmp_path):
    metadata_path, raw_path = input_files(tmp_path)
    project = tmp_path / "project"
    result = subprocess.run(
        [sys.executable, "-m", "src.kb_runtime", "record-source",
         "--metadata", str(metadata_path), "--raw-file", str(raw_path),
         "--project-dir", str(project)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["source_id"] == "SBI_Q1FY27"
    assert (project / "data/registry/sources/SBI_Q1FY27" / f'{output["version_id"]}.json').exists()
