"""SQLite layer for proposals, decisions, and run history."""
import json
import os
import sqlite3
from datetime import datetime, timezone

from pipeline import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    summary_json TEXT
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    first_run_id TEXT,
    last_run_id TEXT,
    ptype TEXT,
    target TEXT,
    classification TEXT,
    tier TEXT,
    status TEXT DEFAULT 'pending',
    stale INTEGER DEFAULT 0,
    payload_json TEXT,
    changes_json TEXT,
    evidence_json TEXT,
    created_at TEXT,
    decided_at TEXT,
    applied_at TEXT,
    api_response TEXT
);
"""

DECIDED_STATUSES = ("approved", "rejected", "applied", "failed")


def _now():
    return datetime.now(timezone.utc).isoformat()


def connect(db_path=None):
    path = db_path or config.DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def record_run(conn, run_id, summary):
    conn.execute(
        "INSERT OR REPLACE INTO runs (run_id, started_at, finished_at, summary_json)"
        " VALUES (?, COALESCE((SELECT started_at FROM runs WHERE run_id=?), ?), ?, ?)",
        (run_id, run_id, _now(), _now(), json.dumps(summary)),
    )
    conn.commit()


def upsert_proposals(conn, run_id, proposals):
    """Idempotent sync of generated proposals into the store.

    - id already decided/applied  -> skip entirely (never re-open).
    - id exists as pending        -> refresh evidence/payload, clear stale.
    - new id                      -> insert as pending.
    - pending ids NOT regenerated this run -> condition gone -> stale=1.
    Returns counts for the run summary.
    """
    inserted = refreshed = skipped = 0
    seen = set()
    for p in proposals:
        seen.add(p["proposal_id"])
        row = conn.execute(
            "SELECT status FROM proposals WHERE proposal_id=?", (p["proposal_id"],)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO proposals (proposal_id, first_run_id, last_run_id,"
                " ptype, target, classification, tier, status, stale,"
                " payload_json, changes_json, evidence_json, created_at)"
                " VALUES (?,?,?,?,?,?,?, 'pending', 0, ?,?,?,?)",
                (p["proposal_id"], run_id, run_id, p["type"], p["target"],
                 p["classification"], p["tier"], json.dumps(p["payload"]),
                 json.dumps(p["changes"]), json.dumps(p["evidence"]), _now()),
            )
            inserted += 1
        elif row["status"] == "pending":
            conn.execute(
                "UPDATE proposals SET last_run_id=?, tier=?, classification=?,"
                " payload_json=?, changes_json=?, evidence_json=?, stale=0"
                " WHERE proposal_id=?",
                (run_id, p["tier"], p["classification"], json.dumps(p["payload"]),
                 json.dumps(p["changes"]), json.dumps(p["evidence"]),
                 p["proposal_id"]),
            )
            refreshed += 1
        else:
            skipped += 1

    cur = conn.execute(
        "UPDATE proposals SET stale=1 WHERE status='pending' AND last_run_id != ?",
        (run_id,),
    )
    conn.commit()
    return {"inserted": inserted, "refreshed": refreshed,
            "skipped_decided": skipped, "marked_stale": cur.rowcount}


def _row_to_dict(row):
    d = dict(row)
    for key in ("payload_json", "changes_json", "evidence_json"):
        d[key.replace("_json", "")] = json.loads(d.pop(key) or "null")
    return d


def get_proposal(conn, proposal_id):
    row = conn.execute(
        "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_proposals(conn, status=None, include_stale=False):
    q = "SELECT * FROM proposals WHERE 1=1"
    args = []
    if status:
        q += " AND status=?"
        args.append(status)
    if not include_stale:
        q += " AND stale=0"
    q += (" ORDER BY CASE tier WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1"
          " ELSE 2 END, classification, target")
    return [_row_to_dict(r) for r in conn.execute(q, args).fetchall()]


def list_stale_pending(conn):
    rows = conn.execute(
        "SELECT * FROM proposals WHERE status='pending' AND stale=1"
        " ORDER BY tier, target"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def set_decision(conn, proposal_id, status):
    conn.execute(
        "UPDATE proposals SET status=?, decided_at=? WHERE proposal_id=?",
        (status, _now(), proposal_id),
    )
    conn.commit()


def set_applied(conn, proposal_id, ok, api_response):
    conn.execute(
        "UPDATE proposals SET status=?, applied_at=?, api_response=?"
        " WHERE proposal_id=?",
        ("applied" if ok else "failed", _now(),
         json.dumps(api_response), proposal_id),
    )
    conn.commit()


def last_run(conn):
    row = conn.execute(
        "SELECT * FROM runs ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["summary"] = json.loads(d.pop("summary_json") or "null")
    return d
