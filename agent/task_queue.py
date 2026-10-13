"""Task queue: holds pending, running, and completed tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class Step:
    """A single action step within a task."""
    action: str
    params: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Step(action={self.action!r}, params={self.params})"


@dataclass
class Task:
    """A named, ordered collection of steps."""
    name: str
    steps: List[Step] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: TaskStatus = TaskStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"Task(id={self.task_id!r}, name={self.name!r}, "
            f"steps={len(self.steps)}, status={self.status.value})"
        )


class TaskQueue:
    """
    Simple FIFO queue for Task objects.

    Tasks transition:
      PENDING -> RUNNING -> COMPLETED | FAILED | ABORTED
    """

    def __init__(self) -> None:
        self._pending: List[Task] = []
        self._history: List[Task] = []   # completed / failed / aborted

    # ------------------------------------------------------------------
    # Enqueueing
    # ------------------------------------------------------------------

    def enqueue(self, task: Task) -> None:
        """Add a task to the end of the queue."""
        if task.status != TaskStatus.PENDING:
            raise ValueError(
                f"Only PENDING tasks may be enqueued; got {task.status!r}"
            )
        self._pending.append(task)

    # ------------------------------------------------------------------
    # Dequeueing / peeking
    # ------------------------------------------------------------------

    def peek(self) -> Optional[Task]:
        """Return the next task without removing it."""
        return self._pending[0] if self._pending else None

    def dequeue(self) -> Optional[Task]:
        """Pop the next pending task and mark it RUNNING."""
        if not self._pending:
            return None
        task = self._pending.pop(0)
        task.status = TaskStatus.RUNNING
        return task

    # ------------------------------------------------------------------
    # Finalising
    # ------------------------------------------------------------------

    def complete(self, task: Task) -> None:
        task.status = TaskStatus.COMPLETED
        self._history.append(task)

    def fail(self, task: Task, reason: str = "") -> None:
        task.status = TaskStatus.FAILED
        task.metadata["failure_reason"] = reason
        self._history.append(task)

    def abort(self, task: Task, reason: str = "") -> None:
        task.status = TaskStatus.ABORTED
        task.metadata["abort_reason"] = reason
        self._history.append(task)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def pending_count(self) -> int:
        return len(self._pending)

    def is_empty(self) -> bool:
        return len(self._pending) == 0

    def history(self) -> List[Task]:
        return list(self._history)

    def all_tasks(self) -> List[Task]:
        """All pending + historical tasks."""
        return list(self._pending) + self._history

    def __len__(self) -> int:
        return len(self._pending)

    def __repr__(self) -> str:
        return (
            f"TaskQueue(pending={len(self._pending)}, "
            f"history={len(self._history)})"
        )
