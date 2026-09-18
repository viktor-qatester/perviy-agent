"""Persistent bot state (pending digest, edit mode)."""

from __future__ import annotations

import json
import os
from uuid import uuid4
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Mode = Literal["edit"] | None


@dataclass
class BotState:
    pending_digest: str = ""
    draft_id: str = ""
    published_chunks: int = 0
    mode: Mode = None
    updated_at: str = ""

    @classmethod
    def load(cls, path: Path) -> BotState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            pending_digest=data.get("pending_digest") or "",
            draft_id=data.get("draft_id") or "",
            published_chunks=int(data.get("published_chunks") or 0),
            mode=data.get("mode"),
            updated_at=data.get("updated_at") or "",
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def set_pending(self, digest: str) -> None:
        self.pending_digest = digest
        self.draft_id = uuid4().hex
        self.published_chunks = 0
        self.mode = None

    def clear_pending(self) -> None:
        self.pending_digest = ""
        self.draft_id = ""
        self.published_chunks = 0
        self.mode = None

    def start_edit(self) -> None:
        self.mode = "edit"
