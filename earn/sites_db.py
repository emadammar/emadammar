# earn/sites_db.py
# قاعدة بيانات الأقسام والمواقع (بدون سحب / بدون نقاط)

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DB_PATH = "bot.db"
_lock = threading.Lock()

@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()

def _ensure_column(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {c["name"] for c in cols} if cols else set()
    if col not in names:
        conn.execute(ddl)

def init_sites_db() -> None:
    with _lock, _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS offer_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS offer_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            terms TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY(section_id) REFERENCES offer_sections(id) ON DELETE CASCADE
        )
        """)

        # migrations
        _ensure_column(conn, "offer_sites", "description",
                       "ALTER TABLE offer_sites ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "offer_sites", "terms",
                       "ALTER TABLE offer_sites ADD COLUMN terms TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "offer_sites", "updated_at",
                       "ALTER TABLE offer_sites ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "offer_sites", "is_active",
                       "ALTER TABLE offer_sites ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

# ---------- Sections ----------
def add_section(name: str) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("SECTION_NAME_EMPTY")
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO offer_sections (name, is_active, created_at) VALUES (?, 1, ?)",
            (name, int(time.time()))
        )
        return int(cur.lastrowid)

def list_sections(active_only: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT id, name FROM offer_sections WHERE is_active=1 ORDER BY id DESC LIMIT ?",
                (int(limit),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, is_active FROM offer_sections ORDER BY id DESC LIMIT ?",
                (int(limit),)
            ).fetchall()
        return [dict(r) for r in rows]

def get_section(section_id: int) -> Optional[Dict[str, Any]]:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT id, name, is_active FROM offer_sections WHERE id=?",
            (int(section_id),)
        ).fetchone()
        return dict(row) if row else None

# ---------- Sites ----------
def add_site(section_id: int, name: str, url: str, description: str = "", terms: str = "") -> int:
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or not url:
        raise ValueError("SITE_FIELDS_EMPTY")

    now = int(time.time())
    with _lock, _connect() as conn:
        cur = conn.execute("""
            INSERT INTO offer_sites
            (section_id, name, url, description, terms, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            int(section_id),
            name,
            url,
            (description or "").strip(),
            (terms or "").strip(),
            now,
            now
        ))
        return int(cur.lastrowid)

def list_sites_by_section(section_id: int, active_only: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
    with _lock, _connect() as conn:
        if active_only:
            rows = conn.execute("""
                SELECT id, section_id, name, url, description, terms
                FROM offer_sites
                WHERE section_id=? AND is_active=1
                ORDER BY id DESC LIMIT ?
            """, (int(section_id), int(limit))).fetchall()
        else:
            rows = conn.execute("""
                SELECT *
                FROM offer_sites
                WHERE section_id=?
                ORDER BY id DESC LIMIT ?
            """, (int(section_id), int(limit))).fetchall()
        return [dict(r) for r in rows]

def get_site(site_id: int) -> Optional[Dict[str, Any]]:
    with _lock, _connect() as conn:
        row = conn.execute("""
            SELECT id, section_id, name, url, description, terms, is_active
            FROM offer_sites
            WHERE id=?
        """, (int(site_id),)).fetchone()
        return dict(row) if row else None

def update_site(site_id: int, name: str, url: str, description: str, terms: str) -> None:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute("""
            UPDATE offer_sites
            SET name=?, url=?, description=?, terms=?, updated_at=?
            WHERE id=?
        """, (
            (name or "").strip(),
            (url or "").strip(),
            (description or "").strip(),
            (terms or "").strip(),
            now,
            int(site_id)
        ))

def deactivate_site(site_id: int) -> None:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute("""
            UPDATE offer_sites
            SET is_active=0, updated_at=?
            WHERE id=?
        """, (now, int(site_id)))