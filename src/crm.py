"""
CRM database module — SQLite-backed storage for potential SFG customers.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent.parent / "crm.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT,
                company     TEXT,
                email       TEXT,
                phone       TEXT,
                website     TEXT,
                location    TEXT,
                industry    TEXT,
                description TEXT,
                source_url  TEXT,
                tags        TEXT,       -- JSON array
                status      TEXT DEFAULT 'new',
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS search_runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT,
                results_count INTEGER,
                ran_at      TEXT DEFAULT (datetime('now'))
            );
        """)


def upsert_lead(
    name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None,
    location: Optional[str] = None,
    industry: Optional[str] = None,
    description: Optional[str] = None,
    source_url: Optional[str] = None,
    tags: Optional[list] = None,
    notes: Optional[str] = None,
) -> int:
    """Insert a lead or update if the same company+email already exists."""
    tags_json = json.dumps(tags or [])
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        existing = None
        if company or email:
            row = conn.execute(
                "SELECT id FROM leads WHERE company = ? OR (email IS NOT NULL AND email = ?)",
                (company, email),
            ).fetchone()
            if row:
                existing = row["id"]

        if existing:
            conn.execute(
                """UPDATE leads SET
                    name=COALESCE(?,name), company=COALESCE(?,company),
                    email=COALESCE(?,email), phone=COALESCE(?,phone),
                    website=COALESCE(?,website), location=COALESCE(?,location),
                    industry=COALESCE(?,industry), description=COALESCE(?,description),
                    source_url=COALESCE(?,source_url), tags=?, notes=COALESCE(?,notes),
                    updated_at=?
                WHERE id=?""",
                (
                    name, company, email, phone, website, location,
                    industry, description, source_url, tags_json, notes, now, existing,
                ),
            )
            return existing
        else:
            cursor = conn.execute(
                """INSERT INTO leads
                    (name, company, email, phone, website, location,
                     industry, description, source_url, tags, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    name, company, email, phone, website, location,
                    industry, description, source_url, tags_json, notes, now, now,
                ),
            )
            return cursor.lastrowid


def log_search_run(query: str, results_count: int):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO search_runs (query, results_count) VALUES (?,?)",
            (query, results_count),
        )


def get_all_leads(status: Optional[str] = None) -> list[dict]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM leads WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY created_at DESC"
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d.get("tags") or "[]")
        result.append(d)
    return result


def update_lead_status(lead_id: int, status: str, notes: Optional[str] = None):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status=?, notes=COALESCE(?,notes), updated_at=? WHERE id=?",
            (status, notes, now, lead_id),
        )


def get_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM leads GROUP BY status"
        ).fetchall()
        runs = conn.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
    return {
        "total_leads": total,
        "by_status": {row["status"]: row["cnt"] for row in by_status},
        "search_runs": runs,
    }
