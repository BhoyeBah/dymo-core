from typing import Dict, List, Callable, Any, Optional
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import structlog

from dymo_saas_core.models.models import OutboxEvent

logger = structlog.get_logger(__name__)

# In-memory subscriber registry
_SUBSCRIBERS: Dict[str, List[Callable[[Session, OutboxEvent], None]]] = {}

def subscribe(event_key: str, handler: Callable[[Session, OutboxEvent], None]) -> None:
    """
    Register an event subscriber/listener.
    """
    if event_key not in _SUBSCRIBERS:
        _SUBSCRIBERS[event_key] = []
    _SUBSCRIBERS[event_key].append(handler)
    logger.info("Event subscriber registered", event_key=event_key, handler=handler.__name__)

def emit_event(db: Session, event_key: str, payload: dict, tenant_id: Optional[uuid.UUID] = None) -> OutboxEvent:
    """
    Save an outbox event in the database within the current transaction.
    """
    event = OutboxEvent(
        tenant_id=tenant_id,
        event_key=event_key,
        payload=payload,
        status="pending",
        attempt_count=0,
        next_retry_at=datetime.now(timezone.utc)
    )
    db.add(event)
    logger.debug("Outbox event emitted", event_key=event_key, tenant_id=str(tenant_id) if tenant_id else None)
    return event

def process_outbox_events(db: Session, max_retries: int = 3) -> int:
    """
    Fetch and process pending outbox events.
    Returns the number of processed events.
    """
    now = datetime.now(timezone.utc)
    
    # Query pending or retryable failed events
    events = db.query(OutboxEvent).filter(
        (OutboxEvent.status == "pending") |
        ((OutboxEvent.status == "failed") & (OutboxEvent.attempt_count < max_retries) & (OutboxEvent.next_retry_at <= now))
    ).limit(50).all()
    
    if not events:
        return 0
        
    processed_count = 0
    for event in events:
        event.status = "processing"
        event.attempt_count += 1
        db.commit() # Update status to processing immediately to avoid concurrent runs
        
        try:
            handlers = _SUBSCRIBERS.get(event.event_key, [])
            if not handlers:
                logger.warning("No handlers registered for outbox event", event_key=event.event_key)
            else:
                for handler in handlers:
                    handler(db, event)
            
            # Mark as processed
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            event.last_error = None
            processed_count += 1
        except Exception as e:
            logger.exception("Error processing outbox event", event_id=str(event.id), event_key=event.event_key)
            event.status = "failed"
            event.last_error = str(e)
            # Exponential backoff retry delay
            backoff_seconds = 2 ** event.attempt_count
            event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            
        db.commit()
        
    return processed_count
