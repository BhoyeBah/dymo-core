from datetime import datetime, timezone
import structlog
from sqlalchemy.orm import Session
from dymo_saas_core.models.models import IdempotencyKey, TenantInvitation

logger = structlog.get_logger(__name__)

def cleanup_expired_idempotency_keys(db: Session) -> int:
    """
    Deletes expired idempotency keys from the database.
    """
    now = datetime.now(timezone.utc)
    try:
        deleted_count = db.query(IdempotencyKey).filter(
            IdempotencyKey.expires_at < now
        ).delete(synchronize_session=False)
        db.commit()
        if deleted_count > 0:
            logger.info("Cleaned up expired idempotency keys", count=deleted_count)
        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error("Failed to cleanup expired idempotency keys", error=str(e))
        return 0

def cleanup_expired_invitations(db: Session) -> int:
    """
    Deletes expired pending tenant invitations from the database.
    """
    now = datetime.now(timezone.utc)
    try:
        deleted_count = db.query(TenantInvitation).filter(
            TenantInvitation.expires_at < now,
            TenantInvitation.status == "pending"
        ).delete(synchronize_session=False)
        db.commit()
        if deleted_count > 0:
            logger.info("Cleaned up expired pending invitations", count=deleted_count)
        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error("Failed to cleanup expired invitations", error=str(e))
        return 0

def process_scheduled_subscription_changes(db: Session) -> int:
    """
    Applies any scheduled subscription changes (downgrades, cancellations) that are due.
    """
    from datetime import datetime, timezone, timedelta
    from dymo_saas_core.models.models import SubscriptionScheduledChange, Subscription, SubscriptionEvent
    from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache

    now = datetime.now(timezone.utc)
    try:
        changes = db.query(SubscriptionScheduledChange).filter(
            SubscriptionScheduledChange.execute_at <= now,
            SubscriptionScheduledChange.is_executed == False
        ).all()
        
        executed_count = 0
        for change in changes:
            sub = db.query(Subscription).filter(Subscription.id == change.subscription_id).first()
            if sub:
                old_plan_id = sub.plan_id
                
                # Apply downgrade / scheduled change
                sub.plan_id = change.target_plan_id
                sub.current_period_start = now
                sub.current_period_end = now + timedelta(days=30)
                sub.cancel_at_period_end = False
                
                # Record event
                event = SubscriptionEvent(
                    tenant_id=change.tenant_id,
                    subscription_id=sub.id,
                    event_type="downgraded" if change.change_type == "downgrade" else change.change_type,
                    old_plan_id=old_plan_id,
                    new_plan_id=change.target_plan_id,
                    notes="Scheduled subscription change executed. Changed from old plan to new plan."
                )
                db.add(event)
                
                # Invalidate cache
                invalidate_tenant_modules_cache(change.tenant_id)
                
                # Mark as executed
                change.is_executed = True
                executed_count += 1
                
        db.commit()
        if executed_count > 0:
            logger.info("Processed scheduled subscription changes", count=executed_count)
        return executed_count
    except Exception as e:
        db.rollback()
        logger.error("Failed to process scheduled subscription changes", error=str(e))
        return 0

