"""Research-only reconstruction from reviewed, exact archive attestations."""

import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .identity_store import DIGEST, _connect, _date, _source, _timestamp, _valid_isin
from .metric_store import SERIES, _decimal, _filing_source, _id, _label, _tables
from .source_store import _hash_file, _read_existing


PROOF_FIELDS = {
    "proof_id", "filing_id", "archive_source_id", "archive_version_id",
    "identity_proof_id", "identity_archive_source_id", "identity_archive_version_id",
    "identity_evidence_locator",
    "evidence_locator", "reviewer_id", "reviewed_at", "review_decision", "proof_category",
}
ARCHIVE_FIELDS = {
    "issuer_id", "isin", "identity_source_id", "identity_version_id",
    "filing_source_id", "filing_version_id", "filing_raw_sha256", "published_at",
}
IDENTITY_ARCHIVE_FIELDS = {
    "issuer_id", "isin", "company_source_id", "company_version_id",
    "security_source_id", "security_version_id", "announced_at",
}
CATEGORY = "MANUAL_REVIEWED_ARCHIVE_ATTESTATION"
TRUST_LIMIT = (
    "Reviewer attests primary exchange origin and historical timestamp; "
    "local metadata and archive authenticity are not independently verified."
)


def _proof_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS backfill_identity_proofs (
            identity_proof_id TEXT PRIMARY KEY, isin TEXT NOT NULL UNIQUE REFERENCES securities(isin),
            issuer_id TEXT NOT NULL REFERENCES companies(issuer_id),
            archive_source_id TEXT NOT NULL, archive_version_id TEXT NOT NULL,
            archive_raw_sha256 TEXT NOT NULL, archive_captured_at TEXT NOT NULL,
            company_source_id TEXT NOT NULL, company_version_id TEXT NOT NULL,
            security_source_id TEXT NOT NULL, security_version_id TEXT NOT NULL,
            evidence_locator TEXT NOT NULL, reviewer_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL, review_decision TEXT NOT NULL,
            proof_category TEXT NOT NULL, recorded_at TEXT NOT NULL,
            CHECK (review_decision='CONFIRMED'),
            CHECK (proof_category='MANUAL_REVIEWED_ARCHIVE_ATTESTATION')
        );
        CREATE TABLE IF NOT EXISTS backfill_proofs (
            proof_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL UNIQUE REFERENCES filings(filing_id),
            identity_proof_id TEXT NOT NULL REFERENCES backfill_identity_proofs(identity_proof_id),
            archive_source_id TEXT NOT NULL, archive_version_id TEXT NOT NULL,
            archive_raw_sha256 TEXT NOT NULL, archive_captured_at TEXT NOT NULL,
            identity_source_id TEXT NOT NULL, identity_version_id TEXT NOT NULL,
            filing_raw_sha256 TEXT NOT NULL, evidence_locator TEXT NOT NULL,
            reviewer_id TEXT NOT NULL, reviewed_at TEXT NOT NULL,
            review_decision TEXT NOT NULL, proof_category TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            CHECK (review_decision='CONFIRMED'),
            CHECK (proof_category='MANUAL_REVIEWED_ARCHIVE_ATTESTATION')
        );
        CREATE TRIGGER IF NOT EXISTS backfill_proofs_no_update BEFORE UPDATE ON backfill_proofs
            BEGIN SELECT RAISE(ABORT, 'backfill proofs are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS backfill_proofs_no_delete BEFORE DELETE ON backfill_proofs
            BEGIN SELECT RAISE(ABORT, 'backfill proofs are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS backfill_identity_proofs_no_update BEFORE UPDATE ON backfill_identity_proofs
            BEGIN SELECT RAISE(ABORT, 'identity proofs are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS backfill_identity_proofs_no_delete BEFORE DELETE ON backfill_identity_proofs
            BEGIN SELECT RAISE(ABORT, 'identity proofs are append-only'); END;
    """)


def _archive(project_dir, source_id, version_id, fields=ARCHIVE_FIELDS):
    version_path = Path(project_dir) / "data/registry/sources" / source_id / f"{version_id}.json"
    try:
        version = _read_existing(version_path)
        if (version["source_id"] != source_id or version["version_id"] != version_id
                or version["source_kind"] != "EXCHANGE_ARCHIVE" or version["entity"] == ""
                or urlparse(version["url"]).hostname not in {
                    "nseindia.com", "www.nseindia.com", "bseindia.com", "www.bseindia.com",
                }):
            raise ValueError("archive source is not a named primary exchange source")
        digest = version["raw_sha256"]
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("archive digest is invalid")
        raw_path = Path(project_dir) / "data/raw/sha256" / digest
        if _hash_file(raw_path) != digest:
            raise ValueError("archive raw bytes differ")
        manifest = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != fields:
            raise ValueError("archive manifest fields are invalid")
        digests = (("identity_version_id", "filing_version_id", "filing_raw_sha256")
                   if fields is ARCHIVE_FIELDS else ("company_version_id", "security_version_id"))
        for key in digests:
            if not isinstance(manifest[key], str) or not DIGEST.fullmatch(manifest[key]):
                raise ValueError("archive digest binding is invalid")
        identifiers = (("issuer_id", "identity_source_id", "filing_source_id") if fields is ARCHIVE_FIELDS
                       else ("issuer_id", "company_source_id", "security_source_id"))
        for key in identifiers:
            _id(manifest[key], key)
        if not _valid_isin(manifest["isin"]):
            raise ValueError("archive ISIN is invalid")
        event_key = "published_at" if fields is ARCHIVE_FIELDS else "announced_at"
        manifest[event_key] = _timestamp(manifest[event_key], event_key)
        observed = _timestamp(version["observed_at"], "observed_at")
        captured = _timestamp(version["retrieved_at"], "retrieved_at")
        if manifest[event_key] > observed or observed > captured:
            raise ValueError("archive timing is inconsistent")
        return version, manifest, captured
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("archive source is missing or invalid") from exc


def _check_binding(db, project_dir, filing, version, manifest):
    security = db.execute("SELECT * FROM securities WHERE isin=?", (filing["isin"],)).fetchone()
    company = db.execute("SELECT * FROM companies WHERE issuer_id=?", (filing["issuer_id"],)).fetchone()
    if security is None or company is None or security["issuer_id"] != filing["issuer_id"]:
        raise ValueError("archive identity does not match filing")
    if (version["entity"] != filing["issuer_id"] or manifest["issuer_id"] != filing["issuer_id"]
            or manifest["isin"] != filing["isin"] or manifest["published_at"] != filing["published_at"]
            or manifest["filing_source_id"] != filing["source_id"]
            or manifest["filing_version_id"] != filing["version_id"]
            or manifest["filing_raw_sha256"] != filing["raw_sha256"]
            or manifest["identity_source_id"] != security["source_id"]
            or manifest["identity_version_id"] != security["version_id"]):
        raise ValueError("archive binding differs from filing or identity")
    if security["review_decision"] != "CONFIRMED" or company["review_decision"] != "CONFIRMED":
        raise ValueError("identity review is missing")
    _source({"source_id": security["source_id"], "version_id": security["version_id"],
             "first_seen_at": security["first_seen_at"]}, project_dir)
    _source({"source_id": company["source_id"], "version_id": company["version_id"],
             "first_seen_at": company["first_seen_at"]}, project_dir)
    if _filing_source(filing, project_dir) != filing["raw_sha256"]:
        raise ValueError("filing raw digest differs")
    return security


def _check_identity_archive(db, project_dir, filing, version, manifest, captured):
    security = db.execute("SELECT * FROM securities WHERE isin=?", (filing["isin"],)).fetchone()
    company = db.execute("SELECT * FROM companies WHERE issuer_id=?", (filing["issuer_id"],)).fetchone()
    if security is None or company is None or security["issuer_id"] != filing["issuer_id"]:
        raise ValueError("identity archive has no matching security")
    if (version["entity"] != filing["issuer_id"] or manifest["issuer_id"] != filing["issuer_id"]
            or manifest["isin"] != filing["isin"]
            or manifest["company_source_id"] != company["source_id"]
            or manifest["company_version_id"] != company["version_id"]
            or manifest["security_source_id"] != security["source_id"]
            or manifest["security_version_id"] != security["version_id"]
            or manifest["announced_at"] != security["announced_at"]
            or security["announced_at"] > captured):
        raise ValueError("identity archive binding differs")
    _source({"source_id": company["source_id"], "version_id": company["version_id"],
             "first_seen_at": company["first_seen_at"]}, project_dir)
    _source({"source_id": security["source_id"], "version_id": security["version_id"],
             "first_seen_at": security["first_seen_at"]}, project_dir)
    return security


def register_backfill_proof(request_path: Path, project_dir: Path, catalog_path: Path) -> dict:
    """Record a reviewed attestation; raw archive authenticity remains a reviewer duty."""
    try:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("backfill proof request must be valid JSON") from exc
    if not isinstance(request, dict) or set(request) != PROOF_FIELDS:
        raise ValueError("backfill proof request fields are invalid")
    for key in ("proof_id", "filing_id", "archive_source_id", "identity_proof_id",
                "identity_archive_source_id", "reviewer_id"):
        _id(request[key], key)
    for key in ("archive_version_id", "identity_archive_version_id"):
        if not isinstance(request[key], str) or not DIGEST.fullmatch(request[key]):
            raise ValueError(f"{key} is invalid")
    _label(request["evidence_locator"], "evidence_locator")
    _label(request["identity_evidence_locator"], "identity_evidence_locator")
    reviewed = _timestamp(request["reviewed_at"], "reviewed_at")
    if request["review_decision"] != "CONFIRMED" or request["proof_category"] != CATEGORY:
        raise ValueError("proof must be a confirmed manual archive attestation")
    version, manifest, captured = _archive(project_dir, request["archive_source_id"], request["archive_version_id"])
    identity_version, identity_manifest, identity_captured = _archive(
        project_dir, request["identity_archive_source_id"], request["identity_archive_version_id"],
        IDENTITY_ARCHIVE_FIELDS)
    if reviewed < max(captured, identity_captured):
        raise ValueError("proof review precedes archive capture")
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        _proof_tables(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            filing = db.execute("SELECT * FROM filings WHERE filing_id=?", (request["filing_id"],)).fetchone()
            if filing is None:
                raise ValueError("filing is missing")
            security = _check_binding(db, project_dir, filing, version, manifest)
            if security["announced_at"] > captured:
                raise ValueError("archive predates security identity announcement")
            _check_identity_archive(db, project_dir, filing, identity_version,
                                    identity_manifest, identity_captured)
            identity_row = {
                "identity_proof_id": request["identity_proof_id"], "isin": filing["isin"],
                "issuer_id": filing["issuer_id"],
                "archive_source_id": request["identity_archive_source_id"],
                "archive_version_id": request["identity_archive_version_id"],
                "archive_raw_sha256": identity_version["raw_sha256"],
                "archive_captured_at": identity_captured,
                "company_source_id": identity_manifest["company_source_id"],
                "company_version_id": identity_manifest["company_version_id"],
                "security_source_id": identity_manifest["security_source_id"],
                "security_version_id": identity_manifest["security_version_id"],
                "evidence_locator": request["identity_evidence_locator"],
                "reviewer_id": request["reviewer_id"], "reviewed_at": reviewed,
                "review_decision": request["review_decision"],
                "proof_category": request["proof_category"],
            }
            old_identity = db.execute("""SELECT * FROM backfill_identity_proofs
                WHERE identity_proof_id=? OR isin=?""",
                (request["identity_proof_id"], filing["isin"])).fetchone()
            if old_identity is not None:
                if any(old_identity[key] != value for key, value in identity_row.items()):
                    raise ValueError("identity proof replay conflicts")
            else:
                identity_row["recorded_at"] = datetime.now(timezone.utc).isoformat()
                db.execute(f"INSERT INTO backfill_identity_proofs ({','.join(identity_row)}) "
                           f"VALUES ({','.join('?' for _ in identity_row)})", tuple(identity_row.values()))
            row = {
                **{key: request[key] for key in (
                    "proof_id", "filing_id", "identity_proof_id",
                    "archive_source_id", "archive_version_id",
                    "evidence_locator", "reviewer_id", "review_decision", "proof_category",
                )},
                "archive_raw_sha256": version["raw_sha256"], "archive_captured_at": captured,
                "identity_source_id": manifest["identity_source_id"],
                "identity_version_id": manifest["identity_version_id"],
                "filing_raw_sha256": manifest["filing_raw_sha256"], "reviewed_at": reviewed,
            }
            existing = db.execute("SELECT * FROM backfill_proofs WHERE proof_id=? OR filing_id=?",
                                  (request["proof_id"], request["filing_id"])).fetchone()
            if existing is not None:
                if any(existing[key] != value for key, value in row.items()):
                    raise ValueError("backfill proof replay conflicts")
            else:
                row["recorded_at"] = datetime.now(timezone.utc).isoformat()
                db.execute(f"INSERT INTO backfill_proofs ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
                           tuple(row.values()))
    return {"proof_id": request["proof_id"], "filing_id": request["filing_id"],
            "proof_category": CATEGORY, "publication_allowed": False, "trust_limit": TRUST_LIMIT}


def query_backfilled_metrics(catalog_path: Path, project_dir: Path, isin: str, metric_name: str,
                             period_end: str, cutoff_timestamp: str) -> list[dict]:
    """Select one proven revision leaf per typed series at a historical cutoff."""
    if not _valid_isin(isin):
        raise ValueError("ISIN is invalid")
    _id(metric_name, "metric_name")
    _date(period_end, "period_end")
    cutoff = _timestamp(cutoff_timestamp, "cutoff_timestamp")
    if not Path(catalog_path).is_file():
        return []
    with closing(_connect(catalog_path)) as db:
        _tables(db)
        _proof_tables(db)
        rows = db.execute("""SELECT m.*, f.issuer_id, f.source_id, f.version_id, f.raw_sha256,
            f.published_at, f.first_seen_at, f.reviewed_at AS filing_reviewed_at,
            f.rights_status, f.review_decision, f.isin AS filing_isin
            FROM metrics m JOIN filings f ON f.filing_id=m.filing_id
            WHERE m.isin=? AND m.metric_name=? AND m.period_end=? AND f.published_at<=?""",
            (isin, metric_name, period_end, cutoff)).fetchall()
        if not rows:
            return []
        grouped = {}
        for row in rows:
            if (row["filing_isin"] != isin or row["rights_status"] != "REVIEWED"
                    or row["review_decision"] != "CONFIRMED"
                    or _decimal(row["value_decimal"]) != row["value_decimal"]):
                raise ValueError("stored backfill metric is invalid")
            proof = db.execute("SELECT * FROM backfill_proofs WHERE filing_id=?", (row["filing_id"],)).fetchone()
            if proof is None:
                raise ValueError("eligible historical metric lacks archive proof")
            identity_proof = db.execute("SELECT * FROM backfill_identity_proofs WHERE identity_proof_id=?",
                                        (proof["identity_proof_id"],)).fetchone()
            if identity_proof is None:
                raise ValueError("eligible historical metric lacks identity archive proof")
            version, manifest, captured = _archive(project_dir, proof["archive_source_id"], proof["archive_version_id"])
            identity_version, identity_manifest, identity_captured = _archive(
                project_dir, identity_proof["archive_source_id"], identity_proof["archive_version_id"],
                IDENTITY_ARCHIVE_FIELDS)
            security = _check_binding(db, project_dir, row, version, manifest)
            _check_identity_archive(db, project_dir, row, identity_version,
                                    identity_manifest, identity_captured)
            now = datetime.now(timezone.utc).isoformat()
            for receipt in (proof, identity_proof):
                _id(receipt["reviewer_id"], "reviewer_id")
                _label(receipt["evidence_locator"], "evidence_locator")
                reviewed_at = _timestamp(receipt["reviewed_at"], "reviewed_at")
                recorded_at = _timestamp(receipt["recorded_at"], "recorded_at")
                if reviewed_at > recorded_at or recorded_at > now:
                    raise ValueError("archive proof review time is invalid")
                if receipt["proof_category"] != CATEGORY or receipt["review_decision"] != "CONFIRMED":
                    raise ValueError("archive proof review is invalid")
            if (captured > cutoff or identity_captured > cutoff
                    or security["announced_at"] > captured
                    or proof["archive_raw_sha256"] != version["raw_sha256"]
                    or proof["archive_captured_at"] != captured
                    or proof["identity_source_id"] != manifest["identity_source_id"]
                    or proof["identity_version_id"] != manifest["identity_version_id"]
                    or proof["filing_raw_sha256"] != manifest["filing_raw_sha256"]
                    or identity_proof["isin"] != isin or identity_proof["issuer_id"] != row["issuer_id"]
                    or identity_proof["archive_raw_sha256"] != identity_version["raw_sha256"]
                    or identity_proof["archive_captured_at"] != identity_captured
                    or identity_proof["company_source_id"] != identity_manifest["company_source_id"]
                    or identity_proof["company_version_id"] != identity_manifest["company_version_id"]
                    or identity_proof["security_source_id"] != identity_manifest["security_source_id"]
                    or identity_proof["security_version_id"] != identity_manifest["security_version_id"]):
                raise ValueError("archive proof does not establish cutoff availability")
            if row["supersedes_metric_id"] is not None:
                predecessor = db.execute("""SELECT m.*, f.published_at FROM metrics m
                    JOIN filings f ON f.filing_id=m.filing_id WHERE m.metric_id=?""",
                    (row["supersedes_metric_id"],)).fetchone()
                if (predecessor is None or any(predecessor[key] != row[key] for key in SERIES)
                        or predecessor["published_at"] >= row["published_at"]):
                    raise ValueError("historical metric predecessor is invalid")
            key = tuple(row[field] for field in SERIES)
            grouped.setdefault(key, []).append((row, proof, identity_proof))
        result = []
        for entries in grouped.values():
            superseded = {row["supersedes_metric_id"] for row, _, _ in entries if row["supersedes_metric_id"]}
            leaves = [(row, proof, identity_proof) for row, proof, identity_proof in entries
                      if row["metric_id"] not in superseded]
            if len(leaves) != 1:
                raise ValueError("historical metric revisions resolve ambiguously")
            row, proof, identity_proof = leaves[0]
            result.append({key: row[key] for key in (
                "metric_id", "filing_id", "isin", "metric_name", "value_decimal", "unit",
                "period_end", "period_kind", "reporting_scope", "value_kind", "evidence_locator",
                "source_id", "version_id", "published_at", "first_seen_at",
            )} | {
                "availability_mode": "BACKFILLED", "proof_id": proof["proof_id"],
                "proof_category": CATEGORY, "proof_reviewed_at": proof["reviewed_at"],
                "archive_source_id": proof["archive_source_id"],
                "archive_version_id": proof["archive_version_id"],
                "archive_captured_at": proof["archive_captured_at"],
                "identity_proof_id": identity_proof["identity_proof_id"],
                "identity_proof_reviewed_at": identity_proof["reviewed_at"],
                "identity_archive_source_id": identity_proof["archive_source_id"],
                "identity_archive_version_id": identity_proof["archive_version_id"],
                "identity_archive_captured_at": identity_proof["archive_captured_at"],
                "reconstructed_at": datetime.now(timezone.utc).isoformat(),
                "publication_allowed": False, "trust_limit": TRUST_LIMIT,
            })
        return sorted(result, key=lambda item: (
            item["period_kind"], item["reporting_scope"], item["unit"], item["value_kind"]))
