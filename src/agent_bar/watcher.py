"""Session store + filesystem watching for the daemon.

State flow: hooks write ~/.local/state/agent-bar/sessions/<cli>-<id>.json;
Gio.FileMonitor picks changes up instantly. A GLib timer polls each session's
transcript for token deltas and expires stale/done sessions.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Optional

from gi.repository import Gio, GLib

from .adapters.base import SessionState, STATUS_DONE, STATUS_NEEDS_YOU
from .paths import sessions_dir, stats_db
from .stats import Stats
from .tokens import EMPTY, TokenTracker, total_tokens

DONE_TTL = 3600          # keep finished sessions visible for 1 h
STALE_TTL = 6 * 3600     # drop sessions with no hook activity for 6 h
POLL_MS = 2000


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}
        self._tracker = TokenTracker()
        self._stats = Stats(stats_db())
        self._listeners: list[Callable[[], None]] = []
        self._emit_pending = False
        self._last_reported: dict[str, dict] = self._load_reported()
        if self._stats.migrated_dedup:
            # keep reported totals consistent with the halved stats rows,
            # otherwise future deltas would go negative and never flush
            for key, vals in self._last_reported.items():
                if key.startswith("kimi-"):
                    for k in vals:
                        vals[k] //= 2
            self._save_reported()
        self._dir = sessions_dir()
        self._monitor = None
        self._load_existing()

    # --- public API ---

    def add_listener(self, cb: Callable[[], None]) -> None:
        self._listeners.append(cb)

    def start(self) -> None:
        self._monitor = self._dir_monitor()
        GLib.timeout_add(POLL_MS, self._tick)

    def stop(self) -> None:
        if self._monitor:
            self._monitor.cancel()
        self._flush_tokens_all()
        self._save_reported()
        self._stats.close()

    # Cumulative tokens already flushed to stats, persisted so a daemon
    # restart doesn't re-count whole transcripts.
    def _reported_path(self) -> Path:
        from .paths import state_dir
        return state_dir() / "reported.json"

    def _load_reported(self) -> dict[str, dict]:
        try:
            return json.loads(self._reported_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_reported(self) -> None:
        try:
            self._reported_path().write_text(
                json.dumps(self._last_reported), encoding="utf-8")
        except OSError:
            pass

    def attention_sessions(self) -> list[SessionState]:
        return [s for s in self.sessions.values() if s.status == STATUS_NEEDS_YOU]

    def today_total(self) -> int:
        from .stats import sum_total
        return sum_total(self._stats.today())

    def stats(self) -> Stats:
        return self._stats

    def last_context(self, st: SessionState) -> int:
        """Input tokens of the session's most recent model call."""
        if not st.transcript:
            return 0
        return self._tracker.last_context(st.transcript, st.cli)

    # --- internals ---

    def _emit(self) -> None:
        # coalesce bursts of hook events into a single UI refresh
        if self._emit_pending:
            return
        self._emit_pending = True

        def fire() -> None:
            self._emit_pending = False
            for cb in self._listeners:
                cb()

        GLib.idle_add(fire)

    def _load_existing(self) -> None:
        for f in self._dir.glob("*.json"):
            self._load_file(f)

    def _load_file(self, path) -> Optional[SessionState]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            st = SessionState.from_json(data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        st.tokens = {}  # tokens are daemon-computed, not trusted from disk
        self.sessions[st.key] = st
        return st

    def _dir_monitor(self) -> Gio.FileMonitor:
        gfile = Gio.File.new_for_path(str(self._dir))

        def on_change(_mon, file, _other, event):
            if event not in (Gio.FileMonitorEvent.CREATED,
                             Gio.FileMonitorEvent.CHANGED,
                             Gio.FileMonitorEvent.DELETED):
                return
            path = file.get_path()
            if not path or not path.endswith(".json"):
                return
            if event == Gio.FileMonitorEvent.DELETED:
                key = os.path.basename(path)[:-5]
                if self.sessions.pop(key, None):
                    self._emit()
                return
            st = self._load_file(Path(path))
            if st:
                st.updated_at = time.time()
                self._emit()

        mon = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        mon.connect("changed", on_change)
        return mon

    def _tick(self) -> bool:
        now = time.time()
        changed = False
        for key, st in list(self.sessions.items()):
            if st.transcript:
                usage = self._tracker.update(st.transcript, st.cli)
                if usage != st.tokens:
                    st.tokens = usage
                    changed = True
            # expire finished / stale sessions
            age = now - st.updated_at
            if (st.status == STATUS_DONE and age > DONE_TTL) or age > STALE_TTL:
                self._expire(key, st)
                changed = True
        self._flush_tokens_all()
        if changed:
            self._save_reported()
            self._emit()
        return True  # keep the timer alive

    def _expire(self, key: str, st: SessionState) -> None:
        self._flush_tokens(st)
        self.sessions.pop(key, None)
        self._last_reported.pop(key, None)
        try:
            (self._dir / f"{key}.json").unlink(missing_ok=True)
        except OSError:
            pass

    def _flush_tokens_all(self) -> None:
        for st in self.sessions.values():
            self._flush_tokens(st)

    def _flush_tokens(self, st: SessionState) -> None:
        """Persist the per-session token delta since the last flush."""
        prev = self._last_reported.get(st.key)
        if not st.tokens:
            return
        if prev is None:
            delta = st.tokens
        else:
            delta = {k: st.tokens.get(k, 0) - prev.get(k, 0) for k in EMPTY}
        if total_tokens(delta) > 0:
            self._stats.add(st.cli, st.session_id, delta,
                            title=st.title or st.cwd.rsplit("/", 1)[-1])
        self._last_reported[st.key] = dict(st.tokens)
