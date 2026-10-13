"""Tests for the Day-2 agent components."""

from __future__ import annotations

import pytest

from agent import (
    ActionLog,
    AgentLoop,
    ActionDispatcher,
    DispatchError,
    SessionManager,
    Step,
    Task,
    TaskQueue,
    TaskStatus,
)
from mock_browser.engine import NavigationError
from mock_browser.portal import MockPortal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session():
    return SessionManager()


@pytest.fixture
def logged_in_session():
    s = SessionManager()
    s.login("admin", "secret")
    return s


@pytest.fixture
def dispatcher(session):
    session.navigate("/login")
    return ActionDispatcher(session.engine)


# ---------------------------------------------------------------------------
# ActionLog
# ---------------------------------------------------------------------------

class TestActionLog:
    def test_record_ok(self):
        log = ActionLog()
        rec = log.record("t1", "navigate", {"url": "/login"}, "ok", result="status=200")
        assert rec.status == "ok"
        assert rec.action == "navigate"
        assert rec.action_id == 1

    def test_counter_increments(self):
        log = ActionLog()
        for i in range(5):
            log.record("t1", "fill_field", {"name": "x"}, "ok")
        assert log.last().action_id == 5
        assert len(log) == 5

    def test_for_task_filters(self):
        log = ActionLog()
        log.record("task-A", "navigate", {}, "ok")
        log.record("task-B", "navigate", {}, "ok")
        log.record("task-A", "fill_field", {}, "ok")
        assert len(log.for_task("task-A")) == 2
        assert len(log.for_task("task-B")) == 1

    def test_to_json_parseable(self):
        import json
        log = ActionLog()
        log.record("t", "navigate", {"url": "/login"}, "ok", result="x")
        data = json.loads(log.to_json())
        assert isinstance(data, list)
        assert data[0]["action"] == "navigate"

    def test_record_error(self):
        log = ActionLog()
        rec = log.record("t", "fill_field", {"name": "bad"}, "error", error="Field not found")
        assert rec.status == "error"
        assert rec.error == "Field not found"


# ---------------------------------------------------------------------------
# TaskQueue
# ---------------------------------------------------------------------------

class TestTaskQueue:
    def test_enqueue_dequeue(self):
        q = TaskQueue()
        t = Task(name="login", steps=[Step("navigate", {"url": "/login"})])
        q.enqueue(t)
        assert len(q) == 1
        got = q.dequeue()
        assert got.task_id == t.task_id
        assert got.status == TaskStatus.RUNNING
        assert len(q) == 0

    def test_peek_does_not_remove(self):
        q = TaskQueue()
        t = Task(name="t", steps=[])
        q.enqueue(t)
        assert q.peek() is t
        assert len(q) == 1

    def test_dequeue_empty_returns_none(self):
        q = TaskQueue()
        assert q.dequeue() is None

    def test_complete_moves_to_history(self):
        q = TaskQueue()
        t = Task(name="t", steps=[])
        q.enqueue(t)
        task = q.dequeue()
        q.complete(task)
        assert task.status == TaskStatus.COMPLETED
        assert task in q.history()

    def test_fail_records_reason(self):
        q = TaskQueue()
        t = Task(name="t", steps=[])
        q.enqueue(t)
        task = q.dequeue()
        q.fail(task, reason="bad thing")
        assert task.status == TaskStatus.FAILED
        assert task.metadata["failure_reason"] == "bad thing"

    def test_enqueue_non_pending_raises(self):
        q = TaskQueue()
        t = Task(name="t", steps=[])
        q.enqueue(t)
        running = q.dequeue()
        with pytest.raises(ValueError):
            q.enqueue(running)

    def test_fifo_order(self):
        q = TaskQueue()
        names = ["a", "b", "c"]
        for n in names:
            q.enqueue(Task(name=n, steps=[]))
        for n in names:
            assert q.dequeue().name == n


# ---------------------------------------------------------------------------
# ActionDispatcher
# ---------------------------------------------------------------------------

class TestActionDispatcher:
    def test_navigate(self, dispatcher):
        result = dispatcher.dispatch("navigate", {"url": "/login"})
        assert "status=200" in result

    def test_fill_and_read_field(self, dispatcher):
        dispatcher.dispatch("fill_field", {"name": "username", "value": "alice"})
        val = dispatcher.dispatch("read_field", {"name": "username"})
        assert val == "alice"

    def test_unknown_action_raises(self, dispatcher):
        with pytest.raises(DispatchError):
            dispatcher.dispatch("explode", {})

    def test_fill_missing_field_raises(self, dispatcher):
        with pytest.raises(NavigationError):
            dispatcher.dispatch("fill_field", {"name": "ghost", "value": "x"})

    def test_click(self, dispatcher, session):
        # Login first to get to dashboard where nav links exist
        session.login("admin", "secret")
        session.navigate("/dashboard")
        # Re-create dispatcher bound to the updated engine
        d = ActionDispatcher(session.engine)
        result = d.dispatch("click", {"element_id": "nav-submit-form"})
        assert "clicked" in result

    def test_submit_form(self, dispatcher):
        dispatcher.dispatch("fill_field", {"name": "username", "value": "admin"})
        dispatcher.dispatch("fill_field", {"name": "password", "value": "secret"})
        result = dispatcher.dispatch("submit_form", {"form_id": "login-form"})
        assert "status=302" in result


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_initial_state(self, session):
        assert not session.is_authenticated
        assert session.current_url == ""

    def test_login_success(self, session):
        ok = session.login("admin", "secret")
        assert ok is True
        assert session.is_authenticated

    def test_login_failure(self, session):
        ok = session.login("admin", "wrong")
        assert ok is False
        assert not session.is_authenticated

    def test_logout(self, logged_in_session):
        assert logged_in_session.is_authenticated
        logged_in_session.logout()
        assert not logged_in_session.is_authenticated

    def test_navigate_after_login(self, logged_in_session):
        resp = logged_in_session.navigate("/dashboard")
        assert resp.status == 200
        assert "Dashboard" in logged_in_session.title

    def test_reset_clears_session(self, logged_in_session):
        logged_in_session.reset()
        assert not logged_in_session.is_authenticated

    def test_fill_and_read(self, session):
        session.navigate("/login")
        session.fill_field("username", "bob")
        assert session.read_field("username") == "bob"


# ---------------------------------------------------------------------------
# AgentLoop – integration
# ---------------------------------------------------------------------------

class TestAgentLoop:
    def _make_loop(self):
        s = SessionManager()
        return AgentLoop(session=s)

    def test_run_empty_queue(self):
        loop = self._make_loop()
        executed = loop.run()
        assert executed == []

    def test_run_single_navigate_task(self):
        loop = self._make_loop()
        task = Task(
            name="open-login",
            steps=[Step("navigate", {"url": "/login"})],
        )
        loop.enqueue(task)
        loop.run()
        assert task.status == TaskStatus.COMPLETED
        recs = loop.log.for_task(task.task_id)
        assert len(recs) == 1
        assert recs[0].status == "ok"

    def test_run_login_task(self):
        loop = self._make_loop()
        task = Task(
            name="login",
            steps=[
                Step("navigate", {"url": "/login"}),
                Step("fill_field", {"name": "username", "value": "admin"}),
                Step("fill_field", {"name": "password", "value": "secret"}),
                Step("submit_form", {"form_id": "login-form"}),
            ],
        )
        loop.enqueue(task)
        loop.run()
        assert task.status == TaskStatus.COMPLETED
        assert loop.session.is_authenticated
        assert len(loop.log.for_task(task.task_id)) == 4

    def test_error_step_marks_task_failed(self):
        loop = self._make_loop()
        task = Task(
            name="bad-task",
            steps=[
                Step("navigate", {"url": "/login"}),
                Step("fill_field", {"name": "nonexistent_field", "value": "x"}),
            ],
        )
        loop.enqueue(task)
        loop.run()
        assert task.status == TaskStatus.FAILED
        recs = loop.log.for_task(task.task_id)
        statuses = [r.status for r in recs]
        assert "ok" in statuses
        assert "error" in statuses

    def test_stop_on_error_skips_remaining_steps(self):
        loop = self._make_loop()  # stop_on_error=True by default
        task = Task(
            name="stop-test",
            steps=[
                Step("navigate", {"url": "/login"}),
                Step("fill_field", {"name": "ghost", "value": "x"}),  # will fail
                Step("fill_field", {"name": "username", "value": "y"}),  # should skip
            ],
        )
        loop.enqueue(task)
        loop.run()
        recs = loop.log.for_task(task.task_id)
        assert recs[-1].status == "skipped"

    def test_continue_on_error_when_flag_off(self):
        loop = AgentLoop(session=SessionManager(), stop_on_error=False)
        task = Task(
            name="no-stop",
            steps=[
                Step("navigate", {"url": "/login"}),
                Step("fill_field", {"name": "ghost", "value": "x"}),  # error
                Step("fill_field", {"name": "username", "value": "admin"}),  # still runs
            ],
        )
        loop.enqueue(task)
        loop.run()
        recs = loop.log.for_task(task.task_id)
        statuses = [r.status for r in recs]
        # Last step should be ok, not skipped
        assert statuses[-1] == "ok"

    def test_multiple_tasks_run_in_order(self):
        loop = self._make_loop()
        names = []
        for i in range(3):
            t = Task(
                name=f"task-{i}",
                steps=[Step("navigate", {"url": "/login"})],
            )
            loop.enqueue(t)

        executed = loop.run()
        assert len(executed) == 3
        assert all(t.status == TaskStatus.COMPLETED for t in executed)

    def test_on_action_hook_called(self):
        called = []
        loop = AgentLoop(
            session=SessionManager(),
            on_action=lambda rec: called.append(rec.action),
        )
        task = Task(
            name="hook-test",
            steps=[
                Step("navigate", {"url": "/login"}),
                Step("fill_field", {"name": "username", "value": "admin"}),
            ],
        )
        loop.enqueue(task)
        loop.run()
        assert called == ["navigate", "fill_field"]

    def test_run_one_processes_single_task(self):
        loop = self._make_loop()
        t1 = Task(name="t1", steps=[Step("navigate", {"url": "/login"})])
        t2 = Task(name="t2", steps=[Step("navigate", {"url": "/login"})])
        loop.enqueue(t1)
        loop.enqueue(t2)
        loop.run_one()
        assert t1.status == TaskStatus.COMPLETED
        assert t2.status == TaskStatus.PENDING
        assert loop.queue.pending_count() == 1

    def test_run_one_empty_returns_none(self):
        loop = self._make_loop()
        assert loop.run_one() is None
