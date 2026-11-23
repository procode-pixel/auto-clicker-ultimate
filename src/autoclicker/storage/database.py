"""SQLite persistence. All user data stays on this computer."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autoclicker.core.hotkeys import DEFAULT_BINDINGS
from autoclicker.core.models import (
    ClickJob,
    Macro,
    Profile,
    SafetyPolicy,
    Workflow,
    new_id,
)
from autoclicker.core.presets import builtin_macro, builtin_profiles, builtin_workflow


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        self._seed()

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS macros (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                png BLOB NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                profile_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                clicks INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed(self) -> None:
        if self.get_setting("seeded") == "1":
            return
        for profile in builtin_profiles():
            self.save_profile(profile)
        macro = builtin_macro()
        self.save_macro(macro)
        workflow = builtin_workflow()
        self.save_workflow(workflow)
        self.set_setting("hotkeys", json.dumps(DEFAULT_BINDINGS))
        self.set_setting("theme", "dark")
        self.set_setting("accent", "#c9863a")
        self.set_setting("language", "en")
        self.set_setting("close_to_tray", "1")
        self.set_setting("start_minimized", "0")
        self.set_setting("playback_speed", "1")
        self.set_setting("notifications", "1")
        self.set_setting("safety", json.dumps(SafetyPolicy().to_dict()))
        self.set_setting("onboarded", "0")
        self.set_setting("seeded", "1")

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return default if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def save_profile(self, profile: Profile) -> None:
        now = _now()
        payload = json.dumps(profile.to_dict())
        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM profiles WHERE id = ?", (profile.id,)
            ).fetchone()
            created = existing["created_at"] if existing else now
            if profile.is_default:
                self._conn.execute("UPDATE profiles SET is_default = 0")
            self._conn.execute(
                """
                INSERT INTO profiles(id, name, is_default, is_builtin, payload, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    is_default = excluded.is_default,
                    is_builtin = excluded.is_builtin,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.id,
                    profile.name,
                    int(profile.is_default),
                    int(profile.is_builtin),
                    payload,
                    created,
                    now,
                ),
            )
            self._conn.commit()

    def delete_profile(self, profile_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            self._conn.commit()

    def profiles(self) -> list[Profile]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM profiles ORDER BY is_default DESC, name"
            ).fetchall()
        return [Profile.from_dict(json.loads(row["payload"])) for row in rows]

    def profile(self, profile_id: str) -> Profile | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return None if row is None else Profile.from_dict(json.loads(row["payload"]))

    def default_profile(self) -> Profile | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM profiles WHERE is_default = 1 LIMIT 1"
            ).fetchone()
        if row is None:
            items = self.profiles()
            return items[0] if items else None
        return Profile.from_dict(json.loads(row["payload"]))

    def save_macro(self, macro: Macro) -> None:
        now = _now()
        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM macros WHERE id = ?", (macro.id,)
            ).fetchone()
            created = existing["created_at"] if existing else now
            self._conn.execute(
                """
                INSERT INTO macros(id, name, payload, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (macro.id, macro.name, json.dumps(macro.to_dict()), created, now),
            )
            self._conn.commit()

    def macros(self) -> list[Macro]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM macros ORDER BY name").fetchall()
        return [Macro.from_dict(json.loads(row["payload"])) for row in rows]

    def macro(self, macro_id: str) -> Macro | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM macros WHERE id = ?", (macro_id,)
            ).fetchone()
        return None if row is None else Macro.from_dict(json.loads(row["payload"]))

    def delete_macro(self, macro_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM macros WHERE id = ?", (macro_id,))
            self._conn.commit()

    def save_workflow(self, workflow: Workflow) -> None:
        now = _now()
        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM workflows WHERE id = ?", (workflow.id,)
            ).fetchone()
            created = existing["created_at"] if existing else now
            self._conn.execute(
                """
                INSERT INTO workflows(id, name, payload, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (workflow.id, workflow.name, json.dumps(workflow.to_dict()), created, now),
            )
            self._conn.commit()

    def workflows(self) -> list[Workflow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload FROM workflows ORDER BY name"
            ).fetchall()
        return [Workflow.from_dict(json.loads(row["payload"])) for row in rows]

    def workflow(self, workflow_id: str) -> Workflow | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
        return None if row is None else Workflow.from_dict(json.loads(row["payload"]))

    def delete_workflow(self, workflow_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            self._conn.commit()

    def save_template(self, name: str, png: bytes, template_id: str | None = None) -> str:
        if len(png) > 1_500_000:
            raise ValueError("Reference image is larger than 1.5 MB")
        template_id = template_id or new_id()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO templates(id, name, png, created_at) VALUES(?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name = excluded.name, png = excluded.png
                """,
                (template_id, name[:80], png, _now()),
            )
            self._conn.commit()
        return template_id

    def template_png(self, template_id: str) -> bytes | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT png FROM templates WHERE id = ?", (template_id,)
            ).fetchone()
        return None if row is None else bytes(row["png"])

    def add_session(
        self,
        *,
        profile_name: str,
        kind: str,
        started_at: str,
        clicks: int,
        duration_ms: int,
        reason: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions(id, profile_name, kind, started_at, ended_at, clicks, duration_ms, reason)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id(), profile_name, kind, started_at, _now(), int(clicks), int(duration_ms), reason),
            )
            self._conn.commit()

    def sessions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY ended_at DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def log_activity(self, message: str, level: str = "info") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO activity(ts, level, message) VALUES(?, ?, ?)",
                (_now(), level, message[:500]),
            )
            self._conn.execute(
                "DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 300)"
            )
            self._conn.commit()

    def activity(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, level, message FROM activity ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def analytics_summary(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS sessions,
                       COALESCE(SUM(clicks), 0) AS clicks,
                       COALESCE(SUM(duration_ms), 0) AS duration_ms
                FROM sessions
                """
            ).fetchone()
            tops = self._conn.execute(
                """
                SELECT profile_name, COUNT(*) AS uses, COALESCE(SUM(clicks), 0) AS clicks
                FROM sessions GROUP BY profile_name ORDER BY uses DESC LIMIT 5
                """
            ).fetchall()
        duration = int(row["duration_ms"])
        clicks = int(row["clicks"])
        return {
            "sessions": int(row["sessions"]),
            "clicks": clicks,
            "duration_ms": duration,
            "average_cps": (clicks / (duration / 1000.0)) if duration else 0.0,
            "top_profiles": [dict(item) for item in tops],
        }

    def load_safety(self) -> SafetyPolicy:
        raw = self.get_setting("safety")
        if not raw:
            return SafetyPolicy()
        return SafetyPolicy.from_dict(json.loads(raw))

    def save_safety(self, policy: SafetyPolicy) -> None:
        self.set_setting("safety", json.dumps(policy.to_dict()))

    def duplicate_profile(self, profile_id: str, new_name: str) -> Profile:
        source = self.profile(profile_id)
        if source is None:
            raise KeyError(profile_id)
        copy = Profile(
            id=new_id(),
            name=new_name,
            job=ClickJob.from_dict(source.job.to_dict()),
            notes=source.notes,
            macro_id=source.macro_id,
            workflow_id=source.workflow_id,
        )
        self.save_profile(copy)
        return copy
