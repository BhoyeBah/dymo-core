import hmac
import hashlib
import time
import json
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import structlog

from dymo_saas_core.models.models import OutboxEvent, WebhookSubscription, WebhookDelivery
from dymo_saas_core.core.encryption import decrypt_secret

logger = structlog.get_logger(__name__)

def calculate_signature(secret: str, timestamp: str, raw_body: str) -> str:
    message = f"{timestamp}.{raw_body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

def get_webhook_backoff_delay(attempts: int) -> timedelta:
    if attempts == 1:
        return timedelta(minutes=1)
    elif attempts == 2:
        return timedelta(minutes=5)
    elif attempts == 3:
        return timedelta(minutes=30)
    elif attempts == 4:
        return timedelta(hours=2)
    return timedelta(hours=12)

def enqueue_webhooks_for_event(db: Session, event: OutboxEvent) -> None:
    """Find all active subscriptions for this tenant and event_key and create pending deliveries."""
    subscriptions = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == event.tenant_id,
        WebhookSubscription.status == "active"
    ).all()

    for sub in subscriptions:
        events_list = sub.events or []
        if event.event_key in events_list or "*" in events_list:
            delivery = WebhookDelivery(
                tenant_id=event.tenant_id,
                webhook_subscription_id=sub.id,
                event_type=event.event_key,
                payload=event.payload,
                status="pending",
                attempt_count=0
            )
            db.add(delivery)
            logger.info(
                "Webhook delivery enqueued",
                subscription_id=str(sub.id),
                event_key=event.event_key,
                tenant_id=str(event.tenant_id)
            )
    db.commit()

def dispatch_webhook_delivery(db: Session, delivery: WebhookDelivery, max_attempts: int = 5) -> None:
    """Send the HTTP POST request to target url with HMAC signature."""
    subscription = db.query(WebhookSubscription).filter(
        WebhookSubscription.id == delivery.webhook_subscription_id
    ).first()

    if not subscription or subscription.status != "active":
        # Subscription was deleted or deactivated
        delivery.status = "failed"
        delivery.last_error = "Subscription deleted or inactive"
        db.commit()
        return

    delivery.attempt_count += 1
    db.commit() # commit early to log the attempt count increment

    raw_secret = decrypt_secret(subscription.encrypted_secret)
    timestamp = str(int(time.time()))
    payload_str = json.dumps(delivery.payload, separators=(',', ':'))
    signature = calculate_signature(raw_secret, timestamp, payload_str)

    headers = {
        "Content-Type": "application/json",
        "X-Dymo-Event": delivery.event_type,
        "X-Dymo-Delivery-Id": str(delivery.id),
        "X-Dymo-Timestamp": timestamp,
        "X-Dymo-Signature": signature,
        "User-Agent": "Dymo-Webhook-Dispatcher/1.0"
    }

    start_time = time.time()
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                subscription.target_url,
                content=payload_str,
                headers=headers
            )
        
        delivery.last_status_code = resp.status_code
        if 200 <= resp.status_code < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.last_error = None
            logger.info(
                "Webhook delivered successfully",
                delivery_id=str(delivery.id),
                subscription_id=str(subscription.id),
                status_code=resp.status_code,
                duration=time.time() - start_time
            )
        else:
            raise httpx.HTTPStatusError(
                f"Non-2xx response: {resp.status_code}",
                request=resp.request,
                response=resp
            )
            
    except Exception as e:
        logger.warning(
            "Webhook delivery failed",
            delivery_id=str(delivery.id),
            subscription_id=str(subscription.id),
            error=str(e),
            duration=time.time() - start_time
        )
        delivery.status = "failed"
        delivery.last_error = str(e)[:1000]
        if hasattr(e, "response") and e.response is not None:
            delivery.last_status_code = e.response.status_code

        if delivery.attempt_count < max_attempts:
            delay = get_webhook_backoff_delay(delivery.attempt_count)
            delivery.next_retry_at = datetime.now(timezone.utc) + delay
            logger.info(
                "Webhook delivery scheduled for retry",
                delivery_id=str(delivery.id),
                attempt=delivery.attempt_count,
                retry_at=delivery.next_retry_at.isoformat()
            )
        else:
            delivery.next_retry_at = None
            logger.error(
                "Webhook delivery reached max attempts",
                delivery_id=str(delivery.id),
                attempts=delivery.attempt_count
            )

    db.commit()
