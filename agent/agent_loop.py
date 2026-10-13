"""Core agent loop: dequeues tasks, dispatches steps, logs results."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .action_log import ActionLog, ActionRecord
from .dispatcher import ActionDispatcher, DispatchError
from .session_manager import SessionManager
from .task_queue import Task, TaskQueue, TaskStatus
from mock_browser.engine import NavigationError

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Orchestrates task execution.

    Workflow per task
    -----------------
    1. Pop the next Task from the TaskQueue.
    2. For each Step in the task, call ActionDispatcher.dispatch().
    3. Record the outcome (ok / error) in the ActionLog.
    4. On any hard error, mark the task FAILED and continue with the next.
    5. On success, mark the task COMPLETED.

    Parameters
    ----------
    session : SessionManager
        Shared portal session used for all tasks.
    queue : TaskQueue | None
        If None, an empty queue is created.
    log : ActionLog | None
        If None, a fresh log is created.
    on_action : Callable | None
        Optional hook called after every ActionRecord is written.
        Signature: ``on_action(record: ActionRecord) -> None``
    stop_on_error : bool
        If True the loop aborts the remaining steps in a task on first error.
        If False it attempts every step regardless.
    """

    def __init__(
        self,
        session: SessionManager,
        queue: Optional[TaskQueue] = None,
        log: Optional[ActionLog] = None,
        on_action: Optional[Callable[[ActionRecord], None]] = None,
        stop_on_error: bool = True,
    ) -> None:
        self.session = session
        self.queue = queue or TaskQueue()
        self.log = log or ActionLog()
        self._on_action = on_action
        self.stop_on_error = stop_on_error
        self._dispatcher = ActionDispatcher(session.engine)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, task: Task) -> None:
        """Convenience wrapper around queue.enqueue."""
        self.queue.enqueue(task)

    def run(self) -> List[Task]:
        """
        Process all pending tasks in order.

        Returns the list of tasks that were executed (in order).
        """
        executed: List[Task] = []
        while not self.queue.is_empty():
            task = self.queue.dequeue()
            logger.info("Starting task %s", task)
            self._run_task(task)
            executed.append(task)
        return executed

    def run_one(self) -> Optional[Task]:
        """
        Process a single task from the queue.

        Returns the task if one was available, else None.
        """
        task = self.queue.dequeue()
        if task is None:
            return None
        logger.info("Starting task %s", task)
        self._run_task(task)
        return task

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _run_task(self, task: Task) -> None:
        """Execute every step in *task*, logging each outcome."""
        task_failed = False

        for step in task.steps:
            if task_failed and self.stop_on_error:
                # Log remaining steps as skipped
                self._write(
                    task_id=task.task_id,
                    action=step.action,
                    params=step.params,
                    status="skipped",
                    result=None,
                    error="skipped due to earlier error",
                )
                continue

            try:
                result = self._dispatcher.dispatch(step.action, step.params)
                rec = self._write(
                    task_id=task.task_id,
                    action=step.action,
                    params=step.params,
                    status="ok",
                    result=result,
                )
                logger.debug("  %s", rec)

            except (DispatchError, NavigationError, TypeError, ValueError) as exc:
                task_failed = True
                rec = self._write(
                    task_id=task.task_id,
                    action=step.action,
                    params=step.params,
                    status="error",
                    error=str(exc),
                )
                logger.warning("  STEP ERROR: %s", rec)

        if task_failed:
            self.queue.fail(task, reason="one or more steps failed")
            logger.info("Task %s FAILED", task.task_id)
        else:
            self.queue.complete(task)
            logger.info("Task %s COMPLETED", task.task_id)

    def _write(
        self,
        task_id: str,
        action: str,
        params: Dict[str, Any],
        status: str,
        result: Any = None,
        error: Optional[str] = None,
    ) -> ActionRecord:
        rec = self.log.record(
            task_id=task_id,
            action=action,
            params=params,
            status=status,
            result=result,
            error=error,
        )
        if self._on_action:
            try:
                self._on_action(rec)
            except Exception:  # noqa: BLE001
                pass  # hooks must never break the loop
        return rec
