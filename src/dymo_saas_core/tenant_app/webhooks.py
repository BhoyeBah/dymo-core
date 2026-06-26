import secrets
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import NotFoundException, AppException
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.models.models import WebhookSubscription, WebhookDelivery
from dymo_saas_core.core.utils import write_audit_log
from dymo_saas_core.core.encryption import encrypt_secret
from dymo_saas_core.core.webhook_dispatcher import dispatch_webhook_delivery
from dymo_saas_core.tenant_app.schemas import (
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionUpdateRequest
)

router = APIRouter(tags=["Tenant Webhooks"])

@router.post("/webhooks", response_model=dict, status_code=201)
def create_webhook_subscription(
    payload: WebhookSubscriptionCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.create"))
):
    raw_secret = secrets.token_hex(32)
    encrypted = encrypt_secret(raw_secret)

    sub = WebhookSubscription(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        target_url=payload.target_url,
        events=payload.events,
        encrypted_secret=encrypted,
        status="active",
        created_by_user_id=current_user.id
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="webhook.create",
        payload={"webhook_subscription_id": str(sub.id), "name": sub.name}
    )

    return success_response({
        "id": str(sub.id),
        "name": sub.name,
        "target_url": sub.target_url,
        "events": sub.events,
        "status": sub.status,
        "disabled_at": sub.disabled_at.isoformat() if sub.disabled_at else None,
        "created_at": sub.created_at.isoformat(),
        "updated_at": sub.updated_at.isoformat(),
        "secret": raw_secret
    })

@router.get("/webhooks", response_model=dict)
def list_webhook_subscriptions(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.view"))
):
    subs = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id
    ).order_by(WebhookSubscription.created_at.desc()).all()

    return success_response([
        {
            "id": str(s.id),
            "name": s.name,
            "target_url": s.target_url,
            "events": s.events,
            "status": s.status,
            "disabled_at": s.disabled_at.isoformat() if s.disabled_at else None,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat()
        }
        for s in subs
    ])

@router.get("/webhooks/{webhook_id}", response_model=dict)
def get_webhook_subscription(
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.view"))
):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id,
        WebhookSubscription.id == webhook_id
    ).first()
    if not sub:
        raise NotFoundException("Webhook subscription not found")

    return success_response({
        "id": str(sub.id),
        "name": sub.name,
        "target_url": sub.target_url,
        "events": sub.events,
        "status": sub.status,
        "disabled_at": sub.disabled_at.isoformat() if sub.disabled_at else None,
        "created_at": sub.created_at.isoformat(),
        "updated_at": sub.updated_at.isoformat()
    })

@router.patch("/webhooks/{webhook_id}", response_model=dict)
def update_webhook_subscription(
    webhook_id: uuid.UUID,
    payload: WebhookSubscriptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.update"))
):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id,
        WebhookSubscription.id == webhook_id
    ).first()
    if not sub:
        raise NotFoundException("Webhook subscription not found")

    if payload.name is not None:
        sub.name = payload.name
    if payload.target_url is not None:
        sub.target_url = payload.target_url
    if payload.events is not None:
        sub.events = payload.events
    if payload.status is not None:
        if payload.status != sub.status:
            sub.status = payload.status
            if payload.status == "inactive":
                sub.disabled_at = datetime.now(timezone.utc)
            else:
                sub.disabled_at = None

    db.commit()
    db.refresh(sub)

    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="webhook.update",
        payload={"webhook_subscription_id": str(sub.id)}
    )

    return success_response({
        "id": str(sub.id),
        "name": sub.name,
        "target_url": sub.target_url,
        "events": sub.events,
        "status": sub.status,
        "disabled_at": sub.disabled_at.isoformat() if sub.disabled_at else None,
        "created_at": sub.created_at.isoformat(),
        "updated_at": sub.updated_at.isoformat()
    })

@router.delete("/webhooks/{webhook_id}", response_model=dict)
def delete_webhook_subscription(
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.delete"))
):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id,
        WebhookSubscription.id == webhook_id
    ).first()
    if not sub:
        raise NotFoundException("Webhook subscription not found")

    db.delete(sub)
    db.commit()

    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="webhook.delete",
        payload={"webhook_subscription_id": str(webhook_id)}
    )

    return success_response(message="Webhook subscription deleted successfully")

@router.post("/webhooks/{webhook_id}/test", response_model=dict)
def test_webhook_subscription(
    webhook_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.test"))
):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id,
        WebhookSubscription.id == webhook_id
    ).first()
    if not sub:
        raise NotFoundException("Webhook subscription not found")

    # Create a processing delivery to prevent outbox worker picking it up
    delivery = WebhookDelivery(
        tenant_id=current_user.tenant_id,
        webhook_subscription_id=sub.id,
        event_type="ping",
        payload={"event": "ping", "timestamp": int(time.time()), "message": "Test ping from Dymo SaaS"},
        status="processing",
        attempt_count=0
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    background_tasks.add_task(dispatch_webhook_delivery, db, delivery)

    return success_response(
        message="Test webhook enqueued successfully",
        data={"delivery_id": str(delivery.id)}
    )

@router.get("/webhooks/{webhook_id}/deliveries", response_model=dict)
def get_webhook_deliveries(
    webhook_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.webhooks.deliveries.view"))
):
    sub = db.query(WebhookSubscription).filter(
        WebhookSubscription.tenant_id == current_user.tenant_id,
        WebhookSubscription.id == webhook_id
    ).first()
    if not sub:
        raise NotFoundException("Webhook subscription not found")

    deliveries = db.query(WebhookDelivery).filter(
        WebhookDelivery.tenant_id == current_user.tenant_id,
        WebhookDelivery.webhook_subscription_id == webhook_id
    ).order_by(WebhookDelivery.created_at.desc()).all()

    return success_response([
        {
            "id": str(d.id),
            "webhook_subscription_id": str(d.webhook_subscription_id),
            "event_type": d.event_type,
            "payload": d.payload,
            "status": d.status,
            "attempt_count": d.attempt_count,
            "last_status_code": d.last_status_code,
            "last_error": d.last_error,
            "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat()
        }
        for d in deliveries
    ])
