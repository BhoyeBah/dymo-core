from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from dymo_saas_core.models.models import Subscription, PlanLimit, UsageCounter
from dymo_saas_core.core.exceptions import QuotaExceededException

def check_limit(db: Session, tenant_id: str, metric_key: str, requested_amount: int = 1) -> bool:
    """
    Check if a tenant has remaining quota for a given metric.
    If the threshold is exceeded and overages are blocked, raises QuotaExceededException.
    """
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status.in_(["active", "trialing"])
    ).first()
    if not sub:
        raise QuotaExceededException("No active subscription found for tenant", "NO_ACTIVE_SUBSCRIPTION")

    limit = db.query(PlanLimit).filter(
        PlanLimit.plan_id == sub.plan_id,
        PlanLimit.metric_key == metric_key
    ).first()
    if not limit:
        # If no limit config exists, assume unlimited
        return True

    counter = db.query(UsageCounter).filter(
        UsageCounter.tenant_id == tenant_id,
        UsageCounter.metric_key == metric_key,
        UsageCounter.period_start == sub.current_period_start,
        UsageCounter.period_end == sub.current_period_end
    ).first()

    current_value = counter.current_value if counter else 0

    if current_value + requested_amount > limit.limit_value:
        if not limit.overage_allowed:
            raise QuotaExceededException(
                f"Quota exceeded for metric '{metric_key}'. Limit: {limit.limit_value}, Current: {current_value}",
                "QUOTA_EXCEEDED"
            )
    return True

def increment_usage(db: Session, tenant_id: str, metric_key: str, increment: int = 1) -> UsageCounter:
    """
    Increment a tenant's usage counter for a given metric.
    """
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status.in_(["active", "trialing"])
    ).first()
    
    now = datetime.now(timezone.utc)
    p_start = sub.current_period_start if sub else now
    p_end = sub.current_period_end if sub else now + timedelta(days=30)

    counter = db.query(UsageCounter).filter(
        UsageCounter.tenant_id == tenant_id,
        UsageCounter.metric_key == metric_key,
        UsageCounter.period_start == p_start,
        UsageCounter.period_end == p_end
    ).first()

    if not counter:
        counter = UsageCounter(
            tenant_id=tenant_id,
            metric_key=metric_key,
            current_value=0,
            period_start=p_start,
            period_end=p_end
        )
        db.add(counter)
        db.flush()

    counter.current_value += increment
    db.commit()
    return counter

