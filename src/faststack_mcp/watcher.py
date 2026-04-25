"""File watcher with debounce — auto-invalidates the index cache when project files change.
Uses watchfiles (optional dependency). Falls back gracefully if not installed.
Debounce default: 1.5 s to avoid CPU churn on rapid saves.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

try:
    from watchfiles import watch as _watchfiles_watch
    _HAS_WATCHFILES = True
except ImportError:
    _HAS_WATCHFILES = False

_watchers: dict[str, threading.Thread] = {}
_stop_events: dict[str, threading.Event] = {}

_DEBOUNCE_S = 1.5


def is_available() -> bool:
    """True if watchfiles is installed."""
    return _HAS_WATCHFILES


def start_watching(
    project_id: str,
    path: str,
    on_change: Callable[[str], None],
    debounce_s: float = _DEBOUNCE_S,
) -> bool:
    """Watch `path`; call `on_change(project_id)` after each debounced change batch.
    Returns False when watchfiles is not installed.
    No-op if already watching this project_id.
    """
    if not _HAS_WATCHFILES:
        return False
    if project_id in _watchers and _watchers[project_id].is_alive():
        return True

    stop = threading.Event()
    _stop_events[project_id] = stop

    def _loop() -> None:
        try:
            for _changes in _watchfiles_watch(path, stop_event=stop):
                if stop.is_set():
                    break
                # Drain further saves within the debounce window before notifying
                time.sleep(debounce_s)
                if not stop.is_set():
                    try:
                        on_change(project_id)
                    except Exception:
                        pass
        except Exception:
            pass

    t = threading.Thread(
        target=_loop,
        daemon=True,
        name=f"faststack-watcher-{project_id[:8]}",
    )
    _watchers[project_id] = t
    t.start()
    return True


def stop_watching(project_id: str) -> None:
    """Stop watching a project. No-op if not watching."""
    evt = _stop_events.pop(project_id, None)
    if evt is not None:
        evt.set()
    _watchers.pop(project_id, None)


def stop_all() -> None:
    """Stop all active watchers."""
    for pid in list(_stop_events):
        stop_watching(pid)


def watching() -> list[str]:
    """Return project_ids currently being watched."""
    return [pid for pid, t in _watchers.items() if t.is_alive()]
