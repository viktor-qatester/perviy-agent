"""Persistent bot state (pending digest, edit mode)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Mode = Literal["edit"] | None


@dataclass
class BotState:
    pending_digest: str = ""
    pending_id: str = ""
    mode: Mode = None
    updated_at: str = ""

    @classmethod
    def load(cls, path: Path) -> BotState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            pending_digest=data.get("pending_digest") or "",
            pending_id=data.get("pending_id") or "",
            mode=data.get("mode"),
            updated_at=data.get("updated_at") or "",
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_pending(self, digest: str, pending_id: str | None = None) -> str:
        self.pending_digest = digest
        self.mode = None
        self.pending_id = pending_id or uuid.uuid4().hex[:12]
        return self.pending_id

    def clear_pending(self) -> None:
        self.pending_digest = ""
        self.pending_id = ""
        self.mode = None

    def matches_hitl_nonce(self, nonce: str) -> bool:
        """True if callback nonce belongs to the current pending digest."""
        return bool(self.pending_digest and self.pending_id and nonce == self.pending_id)

    def start_edit(self) -> None:
        self.mode = "edit"
