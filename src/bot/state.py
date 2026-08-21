"""Persistent bot state (pending digest, edit mode)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Mode = Literal["edit"] | None


@dataclass
class BotState:
    pending_digest: str = ""
    mode: Mode = None
    updated_at: str = ""

    @classmethod
    def load(cls, path: Path) -> BotState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            pending_digest=data.get("pending_digest") or "",
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

    def set_pending(self, digest: str) -> None:
        self.pending_digest = digest
        self.mode = None

    def clear_pending(self) -> None:
        self.pending_digest = ""
        self.mode = None

    def start_edit(self) -> None:
        self.mode = "edit"
