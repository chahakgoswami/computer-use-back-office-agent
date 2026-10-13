"""Action log: records each agent action with timestamp and result."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ActionRecord:
    """Immutable record of a single dispatched action."""
    action_id: int
    task_id: str
    action: str                       # e.g. "navigate", "fill_field"
    params: Dict[str, Any]
    timestamp: str
    status: str                       # "ok" | "error" | "skipped"
    result: Any = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        parts = [
            f"[{self.timestamp}]",
            f"#{self.action_id}",
            f"task={self.task_id}",
            f"action={self.action}",
            f"params={self.params}",
            f"status={self.status}",
        ]
        if self.result is not None:
            parts.append(f"result={self.result!r}")
        if self.error:
            parts.append(f"error={self.error!r}")
        return " ".join(parts)


class ActionLog:
    """Append-only, in-memory log of all action records."""

    def __init__(self) -> None:
        self._records: List[ActionRecord] = []
        self._counter: int = 0

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def record(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        status: str,
        result: Any = None,
        error: Optional[str] = None,
    ) -> ActionRecord:
        """Create and store an ActionRecord; return it."""
        self._counter += 1
        rec = ActionRecord(
            action_id=self._counter,
            task_id=task_id,
            action=action,
            params=params,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=status,
            result=result,
            error=error,
        )
        self._records.append(rec)
        return rec

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def all(self) -> List[ActionRecord]:
        return list(self._records)

    def for_task(self, task_id: str) -> List[ActionRecord]:
        return [r for r in self._records if r.task_id == task_id]

    def last(self) -> Optional[ActionRecord]:
        return self._records[-1] if self._records else None

    def to_json(self, indent: int = 2) -> str:
        return json.dumps([r.as_dict() for r in self._records], indent=indent)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)
