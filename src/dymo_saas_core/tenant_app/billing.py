from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.tenant_context import require_tenant_user
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import NotFoundException, AppException
from dymo_saas_core.core.config import settings
from dymo_saas_core.models.models import (
    Plan, Subscription, SubscriptionEvent, BillingInvoice, UsageCounter, PlanLimit, PlanPrice, SubscriptionScheduledChange
)
from dymo_saas_core.tenant_app.schemas import (
    SubscriptionChangeRequest, StripeCheckoutRequest, StripePortalRequest
)

router = APIRouter(tags=["Tenant Billing"])

@router.get("/subscription")
def get_subscription(db: Session = Depends(get_db), current_user = Depends(require_tenant_user)):
    sub = db.query(Subscription).filter(Subscription.tenant_id == current_user.tenant_id).first()
    if not sub:
        return success_response(None, message="No active subscription found")
        
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    return success_response({
        "id": str(sub.id),
        "plan_id": str(sub.plan_id),
        "plan_name": plan.name if plan else "Unknown",
        "status": sub.status,
        "billing_cycle": sub.billing_cycle,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end": sub.current_period_end.isoformat(),
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end
    })

@router.post("/subscription/change")
def change_subscription(
    body: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    plan = db.query(Plan).filter(Plan.id == body.plan_id, Plan.status == "active").first()
    if not plan:
        raise NotFoundException("Plan not found or inactive", "PLAN_NOT_FOUND")
        
    sub = db.query(Subscription).filter(Subscription.tenant_id == current_user.tenant_id).first()
    
    old_plan_id = None
    now = datetime.now(timezone.utc)
    
    if sub:
        old_plan_id = sub.plan_id
        sub.plan_id = plan.id
        sub.billing_cycle = body.billing_cycle
        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30 if body.billing_cycle == "monthly" else 365)
    else:
        sub = Subscription(
            tenant_id=current_user.tenant_id,
            plan_id=plan.id,
            status="active",
            billing_cycle=body.billing_cycle,
            current_period_start=now,
            current_period_end=now + timedelta(days=30 if body.billing_cycle == "monthly" else 365)
        )
        db.add(sub)
        db.flush()
        
    event = SubscriptionEvent(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        event_type="upgraded" if old_plan_id else "created",
        old_plan_id=old_plan_id,
        new_plan_id=plan.id,
        notes=f"Changed subscription plan to {plan.name}"
    )
    db.add(event)
    db.commit()
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(current_user.tenant_id)
    
    return success_response({
        "subscription_id": str(sub.id),
        "plan_id": str(plan.id),
        "status": sub.status
    }, message="Subscription updated successfully")

@router.post("/subscription/cancel")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    sub = db.query(Subscription).filter(Subscription.tenant_id == current_user.tenant_id).first()
    if not sub:
        raise NotFoundException("Active subscription not found", "SUBSCRIPTION_NOT_FOUND")
        
    sub.cancel_at_period_end = True
    event = SubscriptionEvent(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        event_type="cancelled",
        old_plan_id=sub.plan_id,
        new_plan_id=sub.plan_id,
        notes="Subscription set to cancel at period end"
    )
    db.add(event)
    db.commit()
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(current_user.tenant_id)
    return success_response(None, message="Subscription set to cancel at period end successfully")


@router.post("/subscription/upgrade")
def upgrade_subscription(
    body: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    plan = db.query(Plan).filter(Plan.id == body.plan_id, Plan.status == "active").first()
    if not plan:
        raise NotFoundException("Plan not found or inactive", "PLAN_NOT_FOUND")

    sub = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not sub:
        raise NotFoundException("Active subscription not found to upgrade", "SUBSCRIPTION_NOT_FOUND")
        
    old_plan_id = sub.plan_id
    if old_plan_id == plan.id and sub.billing_cycle == body.billing_cycle:
        raise AppException("Already subscribed to this plan and cycle", "ALREADY_SUBSCRIBED")

    new_price_rec = db.query(PlanPrice).filter(
        PlanPrice.plan_id == plan.id,
        PlanPrice.billing_cycle == body.billing_cycle,
        PlanPrice.is_active == True
    ).first()
    if not new_price_rec:
        raise NotFoundException("New plan price not found for this cycle", "PRICE_NOT_FOUND")
    new_price = float(new_price_rec.amount)

    old_price_rec = db.query(PlanPrice).filter(
        PlanPrice.plan_id == old_plan_id,
        PlanPrice.billing_cycle == sub.billing_cycle,
        PlanPrice.is_active == True
    ).first()
    old_price = float(old_price_rec.amount) if old_price_rec else 0.0

    now = datetime.now(timezone.utc)
    period_start = sub.current_period_start
    if period_start.tzinfo is None:
        period_start = period_start.replace(tzinfo=timezone.utc)
    period_end = sub.current_period_end
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)

    total_days = (period_end - period_start).total_seconds() / 86400.0
    remaining_days = (period_end - now).total_seconds() / 86400.0
    if remaining_days < 0:
        remaining_days = 0.0
    if total_days <= 0:
        total_days = 30.0

    unused_credit = (old_price / total_days) * remaining_days
    charge_amount = max(0.0, new_price - unused_credit)

    sub.plan_id = plan.id
    sub.billing_cycle = body.billing_cycle
    sub.status = "active"
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30 if body.billing_cycle == "monthly" else 365)
    sub.cancel_at_period_end = False

    import random
    invoice_number = f"INV-UP-{random.randint(100000, 999999)}"
    invoice = BillingInvoice(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        invoice_number=invoice_number,
        status="paid" if charge_amount == 0.0 else "open",
        currency=new_price_rec.currency,
        subtotal_amount=charge_amount,
        tax_amount=0.0,
        discount_amount=0.0,
        total_amount=charge_amount,
        amount_paid=charge_amount if charge_amount == 0.0 else 0.0,
        amount_due=0.0 if charge_amount == 0.0 else charge_amount,
        due_date=now + timedelta(days=7),
        period_start=now,
        period_end=sub.current_period_end
    )
    db.add(invoice)

    event = SubscriptionEvent(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        event_type="upgraded",
        old_plan_id=old_plan_id,
        new_plan_id=plan.id,
        notes=f"Upgraded to {plan.name} ({body.billing_cycle}). Prorated charge: {charge_amount:.2f} EUR (credit: {unused_credit:.2f} EUR)"
    )
    db.add(event)
    db.commit()

    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
    invalidate_tenant_modules_cache(current_user.tenant_id)

    return success_response({
        "subscription_id": str(sub.id),
        "plan_id": str(plan.id),
        "status": sub.status,
        "prorated_charge": charge_amount,
        "unused_credit": unused_credit
    }, message="Subscription upgraded successfully")


@router.post("/subscription/downgrade")
def downgrade_subscription(
    body: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    plan = db.query(Plan).filter(Plan.id == body.plan_id, Plan.status == "active").first()
    if not plan:
        raise NotFoundException("Plan not found or inactive", "PLAN_NOT_FOUND")

    sub = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    
    if not sub:
        raise NotFoundException("Active subscription not found to downgrade", "SUBSCRIPTION_NOT_FOUND")

    if sub.plan_id == plan.id and sub.billing_cycle == body.billing_cycle:
        raise AppException("Already subscribed to this plan and cycle", "ALREADY_SUBSCRIBED")

    price_rec = db.query(PlanPrice).filter(
        PlanPrice.plan_id == plan.id,
        PlanPrice.billing_cycle == body.billing_cycle,
        PlanPrice.is_active == True
    ).first()
    if not price_rec:
        raise NotFoundException("Price not found for this cycle", "PRICE_NOT_FOUND")

    db.query(SubscriptionScheduledChange).filter(
        SubscriptionScheduledChange.subscription_id == sub.id,
        SubscriptionScheduledChange.is_executed == False
    ).delete()

    scheduled_change = SubscriptionScheduledChange(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        change_type="downgrade",
        target_plan_id=plan.id,
        execute_at=sub.current_period_end,
        is_executed=False
    )
    db.add(scheduled_change)
    
    event = SubscriptionEvent(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        event_type="downgrade_scheduled",
        old_plan_id=sub.plan_id,
        new_plan_id=plan.id,
        notes=f"Downgrade to {plan.name} ({body.billing_cycle}) scheduled for {sub.current_period_end.isoformat()}"
    )
    db.add(event)
    db.commit()

    return success_response({
        "subscription_id": str(sub.id),
        "scheduled_change_id": str(scheduled_change.id),
        "target_plan_id": str(plan.id),
        "execute_at": sub.current_period_end.isoformat()
    }, message="Downgrade scheduled successfully")


@router.post("/subscription/cancel-downgrade")
def cancel_downgrade(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id
    ).first()
    if not sub:
        raise NotFoundException("Active subscription not found", "SUBSCRIPTION_NOT_FOUND")

    deleted_count = db.query(SubscriptionScheduledChange).filter(
        SubscriptionScheduledChange.subscription_id == sub.id,
        SubscriptionScheduledChange.is_executed == False
    ).delete()

    if deleted_count == 0:
        raise AppException("No pending scheduled downgrade found", "NO_PENDING_DOWNGRADE")

    event = SubscriptionEvent(
        tenant_id=current_user.tenant_id,
        subscription_id=sub.id,
        event_type="downgrade_cancelled",
        old_plan_id=sub.plan_id,
        new_plan_id=sub.plan_id,
        notes="Scheduled plan downgrade cancelled"
    )
    db.add(event)
    db.commit()

    return success_response(None, message="Scheduled downgrade cancelled successfully")


@router.get("/invoices")
def list_invoices(db: Session = Depends(get_db), current_user = Depends(require_permission("billing.view"))):
    invoices = db.query(BillingInvoice).filter(BillingInvoice.tenant_id == current_user.tenant_id).order_by(BillingInvoice.created_at.desc()).all()
    return success_response([
        {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "currency": inv.currency,
            "total_amount": float(inv.total_amount),
            "due_date": inv.due_date.isoformat(),
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None
        }
        for inv in invoices
    ])

@router.get("/usage")
def get_usage(db: Session = Depends(get_db), current_user = Depends(require_tenant_user)):
    sub = db.query(Subscription).filter(Subscription.tenant_id == current_user.tenant_id).first()
    if not sub:
        return success_response([], message="No subscription limit config found")
        
    limits = db.query(PlanLimit).filter(PlanLimit.plan_id == sub.plan_id).all()
    usage_data = []
    
    for lim in limits:
        counter = db.query(UsageCounter).filter(
            UsageCounter.tenant_id == current_user.tenant_id,
            UsageCounter.metric_key == lim.metric_key
        ).order_by(UsageCounter.created_at.desc()).first()
        
        usage_data.append({
            "metric_key": lim.metric_key,
            "limit_value": lim.limit_value,
            "current_value": counter.current_value if counter else 0,
            "overage_allowed": lim.overage_allowed
        })
        
    return success_response(usage_data)

@router.post("/subscription/checkout-session")
def create_stripe_checkout(
    body: StripeCheckoutRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    from dymo_saas_core.models.models import Tenant, PlanPrice
    from dymo_saas_core.integrations.payments.stripe import create_checkout_session
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise NotFoundException("Tenant not found", "TENANT_NOT_FOUND")
        
    # Resolve the Plan's stripe price ID
    price = db.query(PlanPrice).filter(
        PlanPrice.plan_id == body.plan_id,
        PlanPrice.billing_cycle == body.billing_cycle,
        PlanPrice.is_active == True
    ).first()
    
    if not price:
        raise NotFoundException("Plan price not found for this cycle", "PRICE_NOT_FOUND")
        
    if not price.stripe_price_id and settings.STRIPE_API_KEY:
        raise AppException("Stripe price ID is not configured for this price tier", "STRIPE_PRICE_UNCONFIGURED")
        
    price_key = price.stripe_price_id or "price_mock"
    
    session = create_checkout_session(
        db=db,
        tenant=tenant,
        price_id=price_key,
        billing_cycle=body.billing_cycle,
        success_url=body.success_url,
        cancel_url=body.cancel_url
    )
    return success_response(session)

@router.post("/subscription/portal-session")
def create_stripe_portal(
    body: StripePortalRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("billing.manage"))
):
    from dymo_saas_core.models.models import Tenant
    from dymo_saas_core.integrations.payments.stripe import create_billing_portal_session
    
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise NotFoundException("Tenant not found", "TENANT_NOT_FOUND")
        
    if not tenant.stripe_customer_id:
        raise AppException("No billing customer profile found. Please subscribe to a plan first.", "NO_BILLING_PROFILE")
        
    session = create_billing_portal_session(
        tenant=tenant,
        return_url=body.return_url
    )
    return success_response(session)
