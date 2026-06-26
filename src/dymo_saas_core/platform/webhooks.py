import json
import uuid
import stripe
import structlog
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.config import settings
from dymo_saas_core.models.models import (
    Tenant, Subscription, SubscriptionEvent, BillingInvoice, BillingPayment, PlanPrice, Plan
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing/webhooks", tags=["Public Billing Webhooks"])

def parse_stripe_timestamp(ts: Optional[int], fallback: Optional[datetime] = None) -> datetime:
    if ts is None:
        return fallback or datetime.now(timezone.utc)
    return datetime.fromtimestamp(ts, tz=timezone.utc)

@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook receiver endpoint."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    # 1. Parse and verify Stripe event
    event = None
    if settings.STRIPE_API_KEY and settings.STRIPE_WEBHOOK_SECRET and sig_header:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            logger.error("Stripe webhook signature validation failed", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    else:
        # Fallback for development/testing without real signature/secret
        try:
            event_data = json.loads(payload.decode("utf-8"))
            # If we don't have a real stripe webhook secret, wrap it in a mock/dict representation
            event = stripe.Event.construct_from(event_data, settings.STRIPE_API_KEY or "mock_key")
        except Exception as e:
            logger.error("Failed to parse Stripe webhook payload as JSON", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook JSON payload")

    # Convert Stripe event to dictionary to ensure dict-like access works on Stripe v8+ objects
    event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)

    event_type = event_dict.get("type")
    data_object = event_dict.get("data", {}).get("object", {})
    
    logger.info("Processing Stripe webhook event", event_type=event_type, event_id=event_dict.get("id"))
    
    # 2. Handle specific Stripe events
    if event_type == "checkout.session.completed":
        await handle_checkout_session_completed(db, data_object)
    elif event_type == "invoice.paid":
        await handle_invoice_paid(db, data_object)
    elif event_type == "invoice.payment_failed":
        await handle_invoice_payment_failed(db, data_object)
    elif event_type == "customer.subscription.updated":
        await handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(db, data_object)
    else:
        logger.info("Stripe webhook event ignored", event_type=event_type)
        
    return {"status": "success"}

async def handle_checkout_session_completed(db: Session, session: dict):
    metadata = session.get("metadata", {})
    tenant_id_str = metadata.get("tenant_id")
    stripe_price_id = metadata.get("stripe_price_id")
    billing_cycle = metadata.get("billing_cycle", "monthly")
    
    if not tenant_id_str:
        logger.warning("checkout.session.completed: tenant_id not found in metadata", session_id=session.get("id"))
        return
        
    tenant_id = uuid.UUID(tenant_id_str)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        logger.error("checkout.session.completed: Tenant not found in DB", tenant_id=tenant_id_str)
        return
        
    # Update stripe customer id
    tenant.stripe_customer_id = session.get("customer")
    tenant.status = "active"
    
    # Resolve local Plan/Price
    plan_price = None
    if stripe_price_id:
        plan_price = db.query(PlanPrice).filter(PlanPrice.stripe_price_id == stripe_price_id).first()
    if not plan_price:
        # Fallback to finding active default price or first available price
        plan_price = db.query(PlanPrice).filter(PlanPrice.is_active == True).first()
        
    if not plan_price:
        logger.error("checkout.session.completed: No plan price available in DB")
        return
        
    # Get subscription
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    stripe_sub_id = session.get("subscription")
    
    now = datetime.now(timezone.utc)
    # Default end period: +30 days (or 365 days)
    end_date = now + (timedelta(days=365) if billing_cycle == "yearly" else timedelta(days=30))
    
    if sub:
        old_plan_id = sub.plan_id
        sub.plan_id = plan_price.plan_id
        sub.status = "active"
        sub.billing_cycle = billing_cycle
        sub.stripe_subscription_id = stripe_sub_id
        sub.current_period_start = now
        sub.current_period_end = end_date
    else:
        old_plan_id = None
        sub = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_price.plan_id,
            status="active",
            billing_cycle=billing_cycle,
            stripe_subscription_id=stripe_sub_id,
            current_period_start=now,
            current_period_end=end_date,
            payment_provider="stripe"
        )
        db.add(sub)
        
    db.flush()
    
    # Create subscription event
    event = SubscriptionEvent(
        tenant_id=tenant_id,
        subscription_id=sub.id,
        event_type="upgraded" if old_plan_id else "created",
        old_plan_id=old_plan_id,
        new_plan_id=plan_price.plan_id,
        notes=f"Stripe Checkout completed for sub ID {stripe_sub_id}"
    )
    db.add(event)
    db.commit()
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(tenant_id)
    logger.info("Processed checkout.session.completed", tenant_id=tenant_id_str, stripe_sub_id=stripe_sub_id)

async def handle_invoice_paid(db: Session, inv: dict):
    stripe_sub_id = inv.get("subscription")
    if not stripe_sub_id:
        logger.warning("invoice.paid: subscription not found in payload", invoice_id=inv.get("id"))
        return
        
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        logger.error("invoice.paid: Local subscription not found", stripe_sub_id=stripe_sub_id)
        return
        
    tenant_id = sub.tenant_id
    
    # Update Subscription status and period dates
    sub.status = "active"
    period_start = parse_stripe_timestamp(inv.get("period_start", int(datetime.now().timestamp())))
    period_end = parse_stripe_timestamp(inv.get("period_end", int((datetime.now() + timedelta(days=30)).timestamp())))
    
    sub.current_period_start = period_start
    sub.current_period_end = period_end
    
    total = float(inv.get("total", 0)) / 100.0
    paid = float(inv.get("amount_paid", 0)) / 100.0
    due = float(inv.get("amount_due", 0)) / 100.0
    
    # Create/Update BillingInvoice
    invoice_number = inv.get("number", f"INV-{inv.get('id')[-8:]}")
    local_invoice = db.query(BillingInvoice).filter(BillingInvoice.stripe_invoice_id == inv.get("id")).first()
    
    if not local_invoice:
        local_invoice = BillingInvoice(
            tenant_id=tenant_id,
            subscription_id=sub.id,
            invoice_number=invoice_number,
            status="paid" if paid >= total else "open",
            currency=inv.get("currency", "EUR").upper(),
            subtotal_amount=total,
            total_amount=total,
            amount_paid=paid,
            amount_due=due,
            due_date=parse_stripe_timestamp(inv.get("due_date", inv.get("created"))),
            paid_at=parse_stripe_timestamp(inv.get("status_transitions", {}).get("paid_at", int(datetime.now().timestamp()))) if paid >= total else None,
            period_start=period_start,
            period_end=period_end,
            stripe_invoice_id=inv.get("id"),
            pdf_url=inv.get("hosted_invoice_url")
        )
        db.add(local_invoice)
    else:
        local_invoice.status = "paid" if paid >= total else "open"
        local_invoice.amount_paid = paid
        local_invoice.amount_due = due
        if paid >= total:
            local_invoice.paid_at = parse_stripe_timestamp(inv.get("status_transitions", {}).get("paid_at", int(datetime.now().timestamp())))
            
    db.flush()
    
    # Create BillingPayment if paid
    if paid > 0:
        payment = BillingPayment(
            tenant_id=tenant_id,
            invoice_id=local_invoice.id,
            provider_reference=inv.get("payment_intent"),
            payment_method="stripe",
            amount=paid,
            currency=local_invoice.currency,
            status="completed",
            paid_at=local_invoice.paid_at or datetime.now(timezone.utc)
        )
        db.add(payment)
        
    db.commit()
    logger.info("Processed invoice.paid", stripe_sub_id=stripe_sub_id, invoice_number=invoice_number)

async def handle_invoice_payment_failed(db: Session, inv: dict):
    stripe_sub_id = inv.get("subscription")
    if not stripe_sub_id:
        return
        
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        return
        
    # Mark subscription as past_due
    sub.status = "past_due"
    
    # Write subscription event
    event = SubscriptionEvent(
        tenant_id=sub.tenant_id,
        subscription_id=sub.id,
        event_type="payment_failed",
        old_plan_id=sub.plan_id,
        new_plan_id=sub.plan_id,
        notes=f"Stripe invoice payment failed. Invoice: {inv.get('id')}"
    )
    db.add(event)
    db.commit()
    logger.info("Processed invoice.payment_failed", stripe_sub_id=stripe_sub_id)

async def handle_subscription_updated(db: Session, stripe_sub: dict):
    stripe_sub_id = stripe_sub.get("id")
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        return
        
    # Update period dates and status
    sub.status = stripe_sub.get("status", sub.status)
    sub.current_period_start = parse_stripe_timestamp(stripe_sub.get("current_period_start"))
    sub.current_period_end = parse_stripe_timestamp(stripe_sub.get("current_period_end"))
    sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
    if stripe_sub.get("canceled_at"):
        sub.cancelled_at = parse_stripe_timestamp(stripe_sub.get("canceled_at"))
        
    # Check if plan price is updated
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        stripe_price_id = items[0].get("price", {}).get("id")
        if stripe_price_id:
            plan_price = db.query(PlanPrice).filter(PlanPrice.stripe_price_id == stripe_price_id).first()
            if plan_price and plan_price.plan_id != sub.plan_id:
                old_plan_id = sub.plan_id
                sub.plan_id = plan_price.plan_id
                
                # Write upgrade/downgrade event
                event = SubscriptionEvent(
                    tenant_id=sub.tenant_id,
                    subscription_id=sub.id,
                    event_type="upgraded", # simplified
                    old_plan_id=old_plan_id,
                    new_plan_id=plan_price.plan_id,
                    notes=f"Stripe subscription updated to price {stripe_price_id}"
                )
                db.add(event)
                
    db.commit()
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(sub.tenant_id)
    logger.info("Processed customer.subscription.updated", stripe_sub_id=stripe_sub_id, status=sub.status)

async def handle_subscription_deleted(db: Session, stripe_sub: dict):
    stripe_sub_id = stripe_sub.get("id")
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
    if not sub:
        return
        
    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc)
    
    tenant = db.query(Tenant).filter(Tenant.id == sub.tenant_id).first()
    if tenant:
        tenant.status = "suspended"
        
    event = SubscriptionEvent(
        tenant_id=sub.tenant_id,
        subscription_id=sub.id,
        event_type="cancelled",
        old_plan_id=sub.plan_id,
        new_plan_id=sub.plan_id,
        notes="Stripe subscription deleted/cancelled"
    )
    db.add(event)
    db.commit()
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(sub.tenant_id)
    logger.info("Processed customer.subscription.deleted", stripe_sub_id=stripe_sub_id)
