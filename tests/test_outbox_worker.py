import uuid
import pytest
from datetime import datetime, timezone, timedelta
from click.testing import CliRunner

from dymo_saas_core.core.outbox import emit_event, subscribe, _SUBSCRIBERS
from dymo_saas_core.models.models import OutboxEvent
from dymo_saas_core.jobs.outbox_worker import OutboxWorker
from dymo_saas_core.cli import cli

@pytest.fixture(autouse=True)
def cleanup_subscribers():
    # Save original subscribers to prevent test pollution
    original = dict(_SUBSCRIBERS)
    yield
    # Restore original subscribers
    _SUBSCRIBERS.clear()
    _SUBSCRIBERS.update(original)


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def test_outbox_worker_success(db_session):
    # 1. Un event pending est traité et devient processed
    event_key = f"test.event.{uuid.uuid4()}"
    executed_payloads = []

    def test_handler(db, event):
        executed_payloads.append(event.payload)

    subscribe(event_key, test_handler)

    tenant_id = uuid.uuid4()
    payload = {"message": "hello outbox"}
    event = emit_event(db_session, event_key, payload, tenant_id=tenant_id)
    db_session.commit()

    assert event.status == "pending"

    # Run outbox worker once (s'arrête après un cycle)
    worker = OutboxWorker(interval=0.1)
    worker.run(once=True)

    db_session.refresh(event)
    assert event.status == "processed"
    assert event.attempt_count == 1
    assert event.processed_at is not None
    assert event.last_error is None
    assert len(executed_payloads) == 1
    assert executed_payloads[0] == payload


def test_outbox_worker_failure_and_backoff(db_session):
    # 2. Un handler qui échoue marque l’event failed
    # 3. attempt_count augmente après échec
    # 4. next_retry_at est défini après échec
    event_key = f"test.fail.{uuid.uuid4()}"
    
    def failing_handler(db, event):
        raise RuntimeError("Something went wrong processing outbox")

    subscribe(event_key, failing_handler)

    tenant_id = uuid.uuid4()
    payload = {"message": "doomed to fail"}
    event = emit_event(db_session, event_key, payload, tenant_id=tenant_id)
    db_session.commit()

    worker = OutboxWorker(interval=0.1, max_attempts=5)
    worker.run(once=True)

    db_session.refresh(event)
    assert event.status == "failed"
    assert event.attempt_count == 1
    assert "Something went wrong" in event.last_error
    assert event.next_retry_at is not None
    
    # Backoff schedule check: Attempt 1 is +1 minute
    expected_retry_min = _utc_naive(datetime.now(timezone.utc)) + timedelta(seconds=55)
    expected_retry_max = _utc_naive(datetime.now(timezone.utc)) + timedelta(seconds=65)
    assert expected_retry_min <= _utc_naive(event.next_retry_at) <= expected_retry_max


def test_outbox_worker_future_retry_skipped(db_session):
    # 6. Le worker ne traite pas un event dont next_retry_at est dans le futur
    event_key = f"test.future.{uuid.uuid4()}"
    executed = []
    
    def handler(db, event):
        executed.append(event)
        
    subscribe(event_key, handler)

    tenant_id = uuid.uuid4()
    event = emit_event(db_session, event_key, {"val": 1}, tenant_id=tenant_id)
    event.status = "failed"
    event.attempt_count = 1
    event.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_session.commit()

    worker = OutboxWorker(interval=0.1)
    worker.run(once=True)

    db_session.refresh(event)
    assert event.status == "failed"
    assert event.attempt_count == 1  # not incremented because it wasn't picked up
    assert len(executed) == 0


def test_outbox_worker_max_attempts_reached(db_session):
    # 7. Après max_attempts, l’event reste failed sans retry automatique
    event_key = f"test.max.{uuid.uuid4()}"
    
    def failing_handler(db, event):
        raise RuntimeError("Fail again")

    subscribe(event_key, failing_handler)

    tenant_id = uuid.uuid4()
    event = emit_event(db_session, event_key, {"val": 1}, tenant_id=tenant_id)
    event.status = "failed"
    event.attempt_count = 4
    event.next_retry_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    worker = OutboxWorker(interval=0.1, max_attempts=5)
    worker.run(once=True)

    db_session.refresh(event)
    assert event.status == "failed"
    assert event.attempt_count == 5
    assert event.next_retry_at is None  # max attempts reached, no next retry scheduled


def test_outbox_worker_error_isolation(db_session):
    # 8. Le worker ne fait pas tomber toute la boucle si un event échoue
    event_key_fail = f"test.fail.{uuid.uuid4()}"
    event_key_success = f"test.success.{uuid.uuid4()}"
    
    success_executed = []

    def failing_handler(db, event):
        raise RuntimeError("Fail")
        
    def success_handler(db, event):
        success_executed.append(event.payload)

    subscribe(event_key_fail, failing_handler)
    subscribe(event_key_success, success_handler)

    tenant_id = uuid.uuid4()
    event_fail = emit_event(db_session, event_key_fail, {"val": "fail"}, tenant_id=tenant_id)
    event_success = emit_event(db_session, event_key_success, {"val": "success"}, tenant_id=tenant_id)
    db_session.commit()

    worker = OutboxWorker(interval=0.1, batch_size=10)
    worker.run(once=True)

    db_session.refresh(event_fail)
    db_session.refresh(event_success)

    assert event_fail.status == "failed"
    assert event_success.status == "processed"
    assert success_executed == [{"val": "success"}]


def test_outbox_cli_command():
    # Click option arguments verification
    runner = CliRunner()
    result = runner.invoke(cli, ["process-outbox", "--once", "--interval", "0.5", "--batch-size", "10", "--max-attempts", "4"])
    assert result.exit_code == 0
    assert "Starting outbox worker" in result.output
    assert "once=True" in result.output
    assert "interval=0.5" in result.output
    assert "batch_size=10" in result.output
    assert "max_attempts=4" in result.output


# ==============================================================================
# TECHNICAL NOTE ON CONCURRENCY PROTECTION
# ==============================================================================
# To ensure safe multi-instance concurrency in cluster setups (e.g. running 
# multiple replicas of the outbox worker process), we query outbox events with 
# `with_for_update(skip_locked=True)` in PostgreSQL.
# 
# 1. `with_for_update` issues a `SELECT ... FOR UPDATE` statement that locks 
#    the matched rows inside the transaction.
# 2. `skip_locked=True` adds `SKIP LOCKED` to the SQL query. If another worker 
#    instance is currently processing some of the matched events (and holds a 
#    lock on their rows), this worker will skip them immediately rather than 
#    blocking, preventing thread bottlenecks.
# 3. Once selected, our worker updates their status to `processing` and commits 
#    immediately to release row locks, guaranteeing fast row release.
# ==============================================================================
