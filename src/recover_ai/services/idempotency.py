"""Exactly-once execution.

Re-running the pipeline over the same failures -- a retry after a crash, a
scheduled sweep -- must never create a second payment link or send a
second message for a decision that already went out. Each execution is
keyed by `(transaction, final action, policy version)`; the key is
recorded on success and checked before acting.

The store here is a flat JSON set on disk -- deliberately simple. A real
deployment swaps it for Redis or a unique DB constraint; the interface is
the same two calls.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from recover_ai.domain.enums import DiagnosisAction

IDEMPOTENCY_FILENAME = "executed_keys.json"


def execution_key(transaction_id: str, action: DiagnosisAction, policy_version: str) -> str:
    raw = f"{transaction_id}|{action.value}|{policy_version}"
    return "exec_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class IdempotencyStore:
    def __init__(self, keys: set[str] | None = None) -> None:
        self._keys: set[str] = set(keys or ())
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        with self._lock:
            return key in self._keys

    def mark(self, key: str) -> None:
        with self._lock:
            self._keys.add(key)

    def snapshot(self) -> list[str]:
        with self._lock:
            return sorted(self._keys)

    def __len__(self) -> int:
        return len(self._keys)


def idempotency_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / IDEMPOTENCY_FILENAME


def load_idempotency(data_dir: str | Path) -> IdempotencyStore:
    path = idempotency_path(data_dir)
    if not path.exists():
        return IdempotencyStore()
    try:
        raw = json.loads(path.read_text())
        return IdempotencyStore(set(raw)) if isinstance(raw, list) else IdempotencyStore()
    except (json.JSONDecodeError, ValueError):
        return IdempotencyStore()


def save_idempotency(store: IdempotencyStore, data_dir: str | Path) -> Path:
    path = idempotency_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.snapshot(), indent=2))
    return path
