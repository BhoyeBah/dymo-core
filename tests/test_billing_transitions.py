import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.exceptions import register_exception_handlers
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.tenant_app.billing import router as billing_router
from dymo_saas_core.models.models import (
    Tenant, TenantUser, TenantRole, TenantPermission,
    Subscription, Plan, PlanPrice, SubscriptionScheduledChange, SubscriptionEvent, BillingInvoice,
    tenant_user_roles, tenant_role_permissions
)
from dymo_saas_core.core.security import hash_password, create_access_token
from dymo_saas_core.jobs.cleanup import process_scheduled_subscription_changes

# Local FastAPI app for billing tests
test_billing_app = FastAPI()
register_exception_handlers(test_billing_app)
test_billing_app.include_router(billing_router, prefix="/api/v1/app/billing")


@pytest.fixture
def test_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    test_billing_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_billing_app) as client:
        yield client
    test_billing_app.dependency_overrides.clear()


@pytest.fixture
def seed_billing_env(db_session):
    # 1. Create Tenant
    tenant = Tenant(
        name="Transition Corp",
        slug="transitioncorp",
        status="active",
        owner_email="owner@transition.com",
    )
    db_session.add(tenant)
    db_session.flush()

    # 2. Create User
    user = TenantUser(
        tenant_id=tenant.id,
        email="owner@transition.com",
        password_hash=hash_password("OwnerPassword123!"),
        status="active"
    )
    db_session.add(user)
    db_session.flush()

    # 3. Role & Permission Setup
    role = TenantRole(tenant_id=tenant.id, name="owner", description="Owner")
    db_session.add(role)
    db_session.flush()

    # Link user to role
    db_session.execute(tenant_user_roles.insert().values(user_id=user.id, role_id=role.id))

    # Seed Billing Permission
    perm_billing = TenantPermission(code="billing.manage", name="Billing Manage", description="")
    db_session.add(perm_billing)
    db_session.flush()

    # Link permission to role
    db_session.execute(tenant_role_permissions.insert().values(role_id=role.id, permission_id=perm_billing.id))

    # 4. Seed Plans and Prices
    # Standard Plan (20 EUR / month)
    plan_standard = Plan(
        name="Standard Plan",
        slug="standard",
        status="active",
        trial_enabled=False,
    )
    db_session.add(plan_standard)
    db_session.flush()

    price_standard = PlanPrice(
        plan_id=plan_standard.id,
        billing_cycle="monthly",
        currency="EUR",
        amount=20.00,
        is_active=True
    )
    db_session.add(price_standard)

    # Premium Plan (50 EUR / month)
    plan_premium = Plan(
        name="Premium Plan",
        slug="premium",
        status="active",
        trial_enabled=False,
    )
    db_session.add(plan_premium)
    db_session.flush()

    price_premium = PlanPrice(
        plan_id=plan_premium.id,
        billing_cycle="monthly",
        currency="EUR",
        amount=50.00,
        is_active=True
    )
    db_session.add(price_premium)
    db_session.flush()

    # 5. Create Active Subscription on Standard Plan
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan_standard.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=now - timedelta(days=10),  # 10 days ago
        current_period_end=now + timedelta(days=20)    # 20 days left
    )
    db_session.add(subscription)
    db_session.commit()

    return {
        "tenant": tenant,
        "user": user,
        "plan_standard": plan_standard,
        "plan_premium": plan_premium,
        "subscription": subscription
    }


def test_upgrade_subscription_prorata(test_client, seed_billing_env, db_session):
    user = seed_billing_env["user"]
    tenant = seed_billing_env["tenant"]
    premium_plan = seed_billing_env["plan_premium"]

    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Trigger upgrade to Premium Plan
    payload = {
        "plan_id": str(premium_plan.id),
        "billing_cycle": "monthly"
    }
    resp = test_client.post("/api/v1/app/billing/subscription/upgrade", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_id"] == str(premium_plan.id)
    assert data["status"] == "active"
    
    # 20 EUR for 30 days total. 20 days remaining. Unused credit should be around (20 / 30) * 20 = 13.33 EUR.
    # New price is 50 EUR. Prorated charge = 50 - 13.33 = 36.67 EUR.
    prorated_charge = data["prorated_charge"]
    assert 36.00 < prorated_charge < 37.00
    
    # Check DB update
    sub = seed_billing_env["subscription"]
    db_session.refresh(sub)
    assert sub.plan_id == premium_plan.id
    
    # Check invoice created
    invoice = db_session.query(BillingInvoice).filter(BillingInvoice.subscription_id == sub.id).first()
    assert invoice is not None
    assert abs(float(invoice.total_amount) - prorated_charge) < 0.01

    # Check event created
    event = db_session.query(SubscriptionEvent).filter(
        SubscriptionEvent.subscription_id == sub.id,
        SubscriptionEvent.event_type == "upgraded"
    ).first()
    assert event is not None


def test_scheduled_downgrade_and_cancel(test_client, seed_billing_env, db_session):
    user = seed_billing_env["user"]
    tenant = seed_billing_env["tenant"]
    standard_plan = seed_billing_env["plan_standard"]
    sub = seed_billing_env["subscription"]

    # Let's make current plan Premium first
    sub.plan_id = seed_billing_env["plan_premium"].id
    db_session.commit()

    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Trigger downgrade to Standard
    payload = {
        "plan_id": str(standard_plan.id),
        "billing_cycle": "monthly"
    }
    resp = test_client.post("/api/v1/app/billing/subscription/downgrade", json=payload, headers=headers)
    assert resp.status_code == 200
    
    # Verify active plan is still Premium (scheduled change has not executed yet)
    db_session.refresh(sub)
    assert sub.plan_id == seed_billing_env["plan_premium"].id
    
    # Verify SubscriptionScheduledChange is added
    change = db_session.query(SubscriptionScheduledChange).filter(
        SubscriptionScheduledChange.subscription_id == sub.id,
        SubscriptionScheduledChange.is_executed == False
    ).first()
    assert change is not None
    assert change.target_plan_id == standard_plan.id

    # Test Cancel Downgrade
    cancel_resp = test_client.post("/api/v1/app/billing/subscription/cancel-downgrade", headers=headers)
    assert cancel_resp.status_code == 200
    
    # Verify SubscriptionScheduledChange is deleted
    change_after_cancel = db_session.query(SubscriptionScheduledChange).filter(
        SubscriptionScheduledChange.subscription_id == sub.id,
        SubscriptionScheduledChange.is_executed == False
    ).first()
    assert change_after_cancel is None


def test_background_worker_executes_downgrade(test_client, seed_billing_env, db_session):
    user = seed_billing_env["user"]
    tenant = seed_billing_env["tenant"]
    standard_plan = seed_billing_env["plan_standard"]
    premium_plan = seed_billing_env["plan_premium"]
    sub = seed_billing_env["subscription"]

    # Active is Premium
    sub.plan_id = premium_plan.id
    db_session.commit()

    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Schedule downgrade
    payload = {
        "plan_id": str(standard_plan.id),
        "billing_cycle": "monthly"
    }
    test_client.post("/api/v1/app/billing/subscription/downgrade", json=payload, headers=headers)

    # Shift execute_at to 1 hour ago
    change = db_session.query(SubscriptionScheduledChange).filter(
        SubscriptionScheduledChange.subscription_id == sub.id,
        SubscriptionScheduledChange.is_executed == False
    ).first()
    change.execute_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    # Run the background worker
    executed = process_scheduled_subscription_changes(db_session)
    assert executed == 1

    # Verify subscription is now Standard
    db_session.refresh(sub)
    assert sub.plan_id == standard_plan.id

    # Verify change is marked executed
    db_session.refresh(change)
    assert change.is_executed is True

    # Verify event is logged
    event = db_session.query(SubscriptionEvent).filter(
        SubscriptionEvent.subscription_id == sub.id,
        SubscriptionEvent.event_type == "downgraded"
    ).first()
    assert event is not None
