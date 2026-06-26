import click
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import structlog

from dymo_saas_core.core.database import SessionLocal
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanFeature, PlanModule
)
from dymo_saas_core.core.module_registry import sync_modules_to_database, get_registered_modules

logger = structlog.get_logger(__name__)

@click.group()
def cli():
    pass

@cli.command()
def seed():
    """Seed the database with initial admin and plan configurations."""
    click.echo("Starting database seed...")
    from dymo_saas_core.main import app  # Trigger dynamic module registration
    db: Session = SessionLocal()
    try:
        # 1. Seed Platform Admin
        from dymo_saas_core.core.config import settings
        import os
        
        env = getattr(settings, "ENVIRONMENT", "development").lower()
        admin_email = os.environ.get("PLATFORM_ADMIN_EMAIL")
        admin_password = os.environ.get("PLATFORM_ADMIN_PASSWORD")
        
        if env == "production":
            if not admin_email or not admin_password:
                raise RuntimeError(
                    "Database seeding aborted: For production environments, PLATFORM_ADMIN_EMAIL "
                    "and PLATFORM_ADMIN_PASSWORD environment variables must be explicitly defined."
                )
        else:
            if not admin_email:
                admin_email = "admin@dymo.com"
            if not admin_password:
                admin_password = "DymoAdmin2026!"

        admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == admin_email).first()
        if not admin:
            admin = PlatformAdmin(
                email=admin_email,
                password_hash=hash_password(admin_password),
                first_name="Super",
                last_name="Admin",
                is_active=True
            )
            db.add(admin)
            click.echo(f"Seeded Platform Admin: {admin_email}")
        else:
            click.echo("Platform Admin already exists.")
            
        # 2. Sync Registered Modules
        click.echo("Syncing available modules from registry...")
        synced = sync_modules_to_database(db)
        click.echo(f"Synced modules: {synced}")

        # 3. Seed Subscription Plans
        plans_data = [
            {
                "name": "Standard Plan",
                "slug": "standard",
                "description": "Idéal pour les petites et moyennes entreprises",
                "trial_enabled": True,
                "trial_days": 14,
                "display_order": 1,
                "prices": [
                    {"billing_cycle": "monthly", "currency": "EUR", "amount": 49.00},
                    {"billing_cycle": "yearly", "currency": "EUR", "amount": 470.00}
                ],
                "limits": [
                    {"metric_key": "max_users", "limit_value": 10},
                    {"metric_key": "max_documents", "limit_value": 500}
                ],
                "features": [
                    {"feature_key": "cash_register", "name": "Caisse", "description": "Accès au module de caisse standard"}
                ],
                "modules": ["cash_register_simple"]
            },
            {
                "name": "Premium Plan",
                "slug": "premium",
                "description": "Pour les grandes entreprises nécessitant des volumes importants",
                "trial_enabled": False,
                "trial_days": 0,
                "display_order": 2,
                "prices": [
                    {"billing_cycle": "monthly", "currency": "EUR", "amount": 99.00},
                    {"billing_cycle": "yearly", "currency": "EUR", "amount": 950.00}
                ],
                "limits": [
                    {"metric_key": "max_users", "limit_value": 50},
                    {"metric_key": "max_documents", "limit_value": 5000}
                ],
                "features": [
                    {"feature_key": "cash_register", "name": "Caisse illimitée", "description": "Accès au module de caisse Premium"}
                ],
                "modules": ["cash_register_simple"]
            }
        ]

        for p_data in plans_data:
            plan = db.query(Plan).filter(Plan.slug == p_data["slug"]).first()
            if not plan:
                plan = Plan(
                    name=p_data["name"],
                    slug=p_data["slug"],
                    description=p_data["description"],
                    status="active",
                    trial_enabled=p_data["trial_enabled"],
                    trial_days=p_data["trial_days"],
                    display_order=p_data["display_order"]
                )
                db.add(plan)
                db.flush()
                
                # Add Prices
                for price_info in p_data["prices"]:
                    p = PlanPrice(
                        plan_id=plan.id,
                        billing_cycle=price_info["billing_cycle"],
                        currency=price_info["currency"],
                        amount=price_info["amount"],
                        setup_fee=0.0,
                        is_active=True
                    )
                    db.add(p)
                    
                # Add Limits
                for limit_info in p_data["limits"]:
                    l = PlanLimit(
                        plan_id=plan.id,
                        metric_key=limit_info["metric_key"],
                        limit_value=limit_info["limit_value"],
                        period="monthly",
                        overage_allowed=True,
                        overage_unit_price=0.05
                    )
                    db.add(l)
                    
                # Add Features
                for feat_info in p_data["features"]:
                    f = PlanFeature(
                        plan_id=plan.id,
                        feature_key=feat_info["feature_key"],
                        name=feat_info["name"],
                        description=feat_info["description"]
                    )
                    db.add(f)
                    
                # Add Modules
                for mod_key in p_data["modules"]:
                    pm = PlanModule(
                        plan_id=plan.id,
                        module_key=mod_key
                    )
                    db.add(pm)
                    
                click.echo(f"Seeded Subscription Plan: {plan.name}")
            else:
                click.echo(f"Subscription Plan {plan.name} already exists.")
                
        db.commit()
        click.echo("Seeding completed successfully.")
    except Exception as e:
        db.rollback()
        click.echo(f"Seeding failed: {str(e)}")
        logger.exception("Database seeding error")
    finally:
        db.close()

@cli.command("process-outbox")
@click.option("--interval", default=1.0, type=float, help="Polling interval in seconds.")
@click.option("--once", is_flag=True, help="Run once and exit.")
@click.option("--batch-size", default=20, type=int, help="Batch size of events to process.")
@click.option("--max-attempts", default=5, type=int, help="Maximum execution attempts for failed events.")
def process_outbox(interval: float, once: bool, batch_size: int, max_attempts: int):
    """Run background worker to process outbox events."""
    click.echo(f"Starting outbox worker (once={once}, interval={interval}s, batch_size={batch_size}, max_attempts={max_attempts})...")
    try:
        from dymo_saas_core.main import app  # Trigger dynamic module registration
    except Exception as e:
        click.echo(f"Warning: Failed to import main app: {e}")
        
    from dymo_saas_core.jobs.outbox_worker import OutboxWorker
    worker = OutboxWorker(interval=interval, batch_size=batch_size, max_attempts=max_attempts)
    worker.run(once=once)

@cli.command("cleanup-jobs")
def cleanup_jobs():
    """Run database cleanup tasks for expired idempotency keys and invitations."""
    click.echo("Starting database cleanups...")
    db: Session = SessionLocal()
    try:
        from dymo_saas_core.jobs.cleanup import (
            cleanup_expired_idempotency_keys,
            cleanup_expired_invitations
        )
        keys_count = cleanup_expired_idempotency_keys(db)
        invs_count = cleanup_expired_invitations(db)
        click.echo(f"Cleanup completed: deleted {keys_count} expired idempotency keys, {invs_count} expired invitations.")
    except Exception as e:
        click.echo(f"Cleanup failed: {str(e)}")
        logger.exception("Database cleanup error")
    finally:
        db.close()

if __name__ == "__main__":
    cli()
