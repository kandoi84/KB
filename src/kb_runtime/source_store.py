"""Immutable local raw source storage with versioned, reviewable metadata."""

import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse


FIELDS = frozenset({
    "source_id", "entity", "source_kind", "url", "source_date",
    "observed_at", "retrieved_at",
})
IDENTITY = ("entity", "source_kind", "url")


def _metadata(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("metadata must be valid JSON") from exc
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("metadata fields must be: " + ", ".join(sorted(FIELDS)))
    if not isinstance(value["source_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value["source_id"]
    ):
        raise ValueError("source_id must use letters, digits, underscores or hyphens")
    for key in ("entity", "source_kind", "url"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    parsed_url = urlparse(value["url"])
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("url must be an HTTP or HTTPS URL")
    if not isinstance(value["source_date"], str):
        raise ValueError("source_date must be an ISO date")
    try:
        if date.fromisoformat(value["source_date"]).isoformat() != value["source_date"]:
            raise ValueError("source_date must be an ISO date")
    except ValueError as exc:
        raise ValueError("source_date must be an ISO date") from exc
    for key in ("observed_at", "retrieved_at"):
        if not isinstance(value[key], str):
            raise ValueError(f"{key} must be a timezone-aware ISO timestamp")
        try:
            timestamp = datetime.fromisoformat(value[key])
        except ValueError as exc:
            raise ValueError(f"{key} must be a timezone-aware ISO timestamp") from exc
        if timestamp.utcoffset() is None:
            raise ValueError(f"{key} must be a timezone-aware ISO timestamp")
    return value


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _install_once(temp_path, target):
    try:
        os.link(temp_path, target)
    except FileExistsError:
        pass
    finally:
        temp_path.unlink(missing_ok=True)


def _read_existing(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"existing source version is invalid: {path}") from exc
    if not isinstance(value, dict) or set(value) != FIELDS | {"raw_sha256", "version_id"}:
        raise ValueError(f"existing source version is invalid: {path}")
    content = {key: item for key, item in value.items() if key != "version_id"}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if value["version_id"] != expected or path.stem != expected:
        raise ValueError(f"existing source version differs from its digest: {path}")
    return value


def record_source(metadata_path: Path, raw_path: Path, project_dir: Path) -> dict[str, str]:
    """Add one source observation; retries return the same immutable version."""
    metadata = _metadata(metadata_path)
    raw_path = Path(raw_path)
    if not raw_path.is_file():
        raise ValueError("raw file does not exist")
    project_dir = Path(project_dir)
    versions_dir = project_dir / "data/registry/sources" / metadata["source_id"]
    if versions_dir.exists():
        for path in versions_dir.glob("*.json"):
            existing = _read_existing(path)
            if any(existing.get(key) != metadata[key] for key in IDENTITY):
                raise ValueError("source_id identity conflicts with an existing version")

    blob_dir = project_dir / "data/raw/sha256"
    blob_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=blob_dir, prefix=".incoming-", delete=False) as output:
        temp_blob = Path(output.name)
        digest = hashlib.sha256()
        try:
            with raw_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temp_blob.unlink(missing_ok=True)
            raise
    raw_sha256 = digest.hexdigest()
    blob_path = blob_dir / raw_sha256
    _install_once(temp_blob, blob_path)
    if _hash_file(blob_path) != raw_sha256:
        raise ValueError("existing raw blob differs from its digest")

    record = {**metadata, "raw_sha256": raw_sha256}
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    version_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    record["version_id"] = version_id
    versions_dir.mkdir(parents=True, exist_ok=True)
    version_path = versions_dir / f"{version_id}.json"
    if version_path.exists():
        if _read_existing(version_path) != record:
            raise ValueError("existing source version differs; refusing overwrite")
    else:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=versions_dir, prefix=".incoming-", delete=False
        ) as output:
            temp_record = Path(output.name)
            try:
                json.dump(record, output, indent=2, sort_keys=True, ensure_ascii=False)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                temp_record.unlink(missing_ok=True)
                raise
        _install_once(temp_record, version_path)
        if _read_existing(version_path) != record:
            raise ValueError("existing source version differs; refusing overwrite")
    return {"source_id": metadata["source_id"], "version_id": version_id, "raw_sha256": raw_sha256}
