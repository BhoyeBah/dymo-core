import time
import signal
import sys
import threading
from datetime import datetime, timezone, timedelta
import structlog
from sqlalchemy import or_, and_

from dymo_saas_core.core.database import SessionLocal
from dymo_saas_core.core.database import engine as sync_engine
from dymo_saas_core.models.models import OutboxEvent, WebhookDelivery
from dymo_saas_core.core.outbox import _SUBSCRIBERS

logger = structlog.get_logger(__name__)

def get_backoff_delay(attempts: int) -> timedelta:
    if attempts == 1:
        return timedelta(minutes=1)
    elif attempts == 2:
        return timedelta(minutes=5)
    elif attempts == 3:
        return timedelta(minutes=30)
    elif attempts == 4:
        return timedelta(hours=2)
    return timedelta(hours=12)


def _utc_now_for_storage() -> datetime:
    """
    Return a UTC timestamp normalized for the active DB driver.

    SQLite commonly drops timezone information on round-trip, so we store
    a naive UTC timestamp there to keep comparisons stable in tests while
    preserving timezone-aware values on databases that support them.
    """
    now = datetime.now(timezone.utc)
    return now.replace(tzinfo=None) if sync_engine.dialect.name == "sqlite" else now

class OutboxWorker:
    def __init__(self, interval: float = 1.0, batch_size: int = 20, max_attempts: int = 5):
        self.interval = interval
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.running = True

    def stop(self, signum=None, frame=None):
        if signum is not None:
            logger.info("Outbox worker received shutdown signal", signal=signum)
        else:
            logger.info("Outbox worker stopping...")
        self.running = False

    def run(self, once: bool = False):
        logger.info(
            "Outbox worker started",
            interval=self.interval,
            batch_size=self.batch_size,
            max_attempts=self.max_attempts,
            once=once
        )
        
        # Register signal handlers for graceful shutdown (main thread only)
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self.stop)
                signal.signal(signal.SIGTERM, self.stop)
            except ValueError as e:
                logger.warning("Could not register signal handlers", error=str(e))

        while self.running:
            start_time = time.time()
            db = SessionLocal()
            event_ids = []
            delivery_ids = []
            try:
                now = datetime.now(timezone.utc)
                stalled_cutoff = now - timedelta(minutes=10)

                # Query pending, failed ready for retry, or stalled events with FOR UPDATE SKIP LOCKED
                events = db.query(OutboxEvent).filter(
                    or_(
                        OutboxEvent.status == "pending",
                        and_(
                            OutboxEvent.status == "failed",
                            OutboxEvent.attempt_count < self.max_attempts,
                            OutboxEvent.next_retry_at <= now
                        ),
                        and_(
                            OutboxEvent.status == "processing",
                            OutboxEvent.updated_at <= stalled_cutoff
                        )
                    )
                ).with_for_update(skip_locked=True).limit(self.batch_size).all()

                if events:
                    event_ids = [e.id for e in events]
                    # Immediately mark them as processing and commit to release locks
                    for event in events:
                        event.status = "processing"
                        event.updated_at = now

                # Query pending, failed ready for retry, or stalled webhook deliveries
                deliveries = db.query(WebhookDelivery).filter(
                    or_(
                        WebhookDelivery.status == "pending",
                        and_(
                            WebhookDelivery.status == "failed",
                            WebhookDelivery.attempt_count < self.max_attempts,
                            WebhookDelivery.next_retry_at <= now
                        ),
                        and_(
                            WebhookDelivery.status == "processing",
                            WebhookDelivery.updated_at <= stalled_cutoff
                        )
                    )
                ).with_for_update(skip_locked=True).limit(self.batch_size).all()

                if deliveries:
                    delivery_ids = [d.id for d in deliveries]
                    for delivery in deliveries:
                        delivery.status = "processing"
                        delivery.updated_at = now

                if events or deliveries:
                    db.commit()
            except Exception as e:
                db.rollback()
                logger.exception("Error querying/locking outbox events/webhook deliveries")
            finally:
                db.close()

            # Process marked events individually
            if event_ids:
                for event_id in event_ids:
                    if not self.running:
                        break
                    self._process_single_event(event_id)

            # Process marked webhook deliveries individually
            if delivery_ids:
                for delivery_id in delivery_ids:
                    if not self.running:
                        break
                    self._process_single_delivery(delivery_id)

            if once:
                break

            # Sleep control
            elapsed = time.time() - start_time
            sleep_needed = max(0.0, self.interval - elapsed)
            
            sleep_step = 0.1
            slept = 0.0
            while slept < sleep_needed and self.running:
                time.sleep(sleep_step)
                slept += sleep_step

        logger.info("Outbox worker stopped")

    def _process_single_event(self, event_id) -> None:
        """Process a single event in its own database session context."""
        db = SessionLocal()
        try:
            # Fetch the event again inside this session
            event = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
            if not event:
                return

            event.attempt_count += 1
            db.commit()  # commit the attempt count increment

            # Process event
            handlers = _SUBSCRIBERS.get(event.event_key, [])
            if not handlers:
                # Fallback fake/log handler
                logger.warning(
                    "No subscriber registered for event, using fallback logger",
                    event_key=event.event_key,
                    event_id=str(event.id)
                )
                logger.info(
                    "Mock process outbox event",
                    event_key=event.event_key,
                    payload=event.payload
                )
            else:
                for handler in handlers:
                    handler(db, event)

            # Success
            from dymo_saas_core.core.webhook_dispatcher import enqueue_webhooks_for_event
            enqueue_webhooks_for_event(db, event)

            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            event.last_error = None
            db.commit()
            logger.info("Outbox event processed successfully", event_id=str(event.id), event_key=event.event_key)

        except Exception as e:
            db.rollback()
            logger.exception("Error processing outbox event", event_id=str(event_id))
            
            try:
                # Re-fetch event to mark as failed in a clean transaction state
                event = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
                if event:
                    event.status = "failed"
                    event.last_error = str(e)
                    
                    if event.attempt_count < self.max_attempts:
                        delay = get_backoff_delay(event.attempt_count)
                        event.next_retry_at = _utc_now_for_storage() + delay
                        logger.info(
                            "Outbox event scheduled for retry",
                            event_id=str(event.id),
                            attempt=event.attempt_count,
                            retry_at=event.next_retry_at.isoformat()
                        )
                    else:
                        event.next_retry_at = None
                        logger.warning(
                            "Outbox event reached maximum retry attempts and is disabled",
                            event_id=str(event.id),
                            attempts=event.attempt_count
                        )
                    db.commit()
            except Exception as inner_ex:
                db.rollback()
                logger.exception("Error saving failure status for event", event_id=str(event_id))
        finally:
            db.close()

    def _process_single_delivery(self, delivery_id) -> None:
        """Process a single WebhookDelivery in its own database session context."""
        db = SessionLocal()
        try:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            if not delivery:
                return

            from dymo_saas_core.core.webhook_dispatcher import dispatch_webhook_delivery
            dispatch_webhook_delivery(db, delivery, max_attempts=self.max_attempts)

        except Exception:
            logger.exception("Error processing webhook delivery", delivery_id=str(delivery_id))
            try:
                delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
                if delivery:
                    delivery.status = "failed"
                    delivery.updated_at = _utc_now_for_storage()
                    db.commit()
            except Exception:
                db.rollback()
        finally:
            db.close()
