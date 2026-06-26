import pytest
import uuid
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from dymo_saas_core.core.cache import cache_service
from dymo_saas_core.core.cache_helpers import invalidate_tenant_cache, invalidate_user_permissions_cache
from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanModule, Subscription,
    Tenant, TenantUser, TenantRole, TenantPermission, tenant_user_roles
)
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.core.module_registry import sync_modules_to_database

@pytest.fixture(autouse=True)
def seed_test_data(db_session):
    """Seed test-specific database tables within the test transaction."""
    # 1. Seed Platform Admin
    admin = PlatformAdmin(
        email="admin@dymo.com",
        password_hash=hash_password("DymoAdmin2026!"),
        first_name="Super",
        last_name="Admin",
        is_active=True
    )
    db_session.add(admin)
    
    # 2. Sync available modules
    sync_modules_to_database(db_session)
    
    # 3. Seed Plan
    plan = Plan(
        name="Standard Plan",
        slug="standard",
        description="Idéal pour les petites et moyennes entreprises",
        status="active",
        trial_enabled=True,
        trial_days=14,
        display_order=1
    )
    db_session.add(plan)
    db_session.flush()
    
    # Add Price
    price = PlanPrice(
        plan_id=plan.id,
        billing_cycle="monthly",
        currency="EUR",
        amount=49.00
    )
    db_session.add(price)
    
    # Add Limit
    limit = PlanLimit(
        plan_id=plan.id,
        metric_key="max_users",
        limit_value=3,
        period="monthly"
    )
    db_session.add(limit)
    
    # Add Module
    pm = PlanModule(
        plan_id=plan.id,
        module_key="cash_register_simple"
    )
    db_session.add(pm)
    
    db_session.commit()

@pytest.fixture(autouse=True)
def clean_redis():
    """Flush Redis before and after each test to ensure isolation."""
    cache_service.flush()
    yield
    cache_service.flush()

def test_tenant_cache_hit_miss_and_invalidation(client, db_session):
    # 1. Login as Platform Admin
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Provision Tenant
    tenant_payload = {
        "name": "Cache Test Inc",
        "slug": "cachetest",
        "owner_email": "owner@cachetest.com",
        "owner_phone": "+33612345678",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }
    prov_resp = client.post("/api/v1/platform/tenants", json=tenant_payload, headers=headers)
    assert prov_resp.status_code == 200
    tenant_id = prov_resp.json()["data"]["id"]
    
    # Subscribe Tenant to Plan
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    sub = Subscription(
        tenant_id=uuid.UUID(tenant_id),
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()
    
    # 3. Authenticate as Tenant Owner to get a tenant JWT
    tenant_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@cachetest.com",
        "password": "ChangeMe123!"
    }, headers={
        "X-Tenant-Slug": "cachetest"
    })
    assert tenant_login_resp.status_code == 200
    tenant_token = tenant_login_resp.json()["data"]["access_token"]
    tenant_headers = {
        "Authorization": f"Bearer {tenant_token}",
        "X-Tenant-Slug": "cachetest"
    }
    
    # 4. Trigger cache population by calling a tenant-scoped route
    resp = client.get("/api/v1/app/cash-register/sales", headers=tenant_headers)
    assert resp.status_code == 200
    
    # Check that tenant details are cached
    cached_tenant = cache_service.get(f"dymo:tenant:id:{tenant_id}")
    assert cached_tenant is not None
    assert cached_tenant["name"] == "Cache Test Inc"
    
    # 5. Direct DB update (bypassing route invalidation)
    db_tenant = db_session.query(Tenant).filter(Tenant.id == uuid.UUID(tenant_id)).first()
    db_tenant.name = "Cache Test Updated Name"
    db_session.commit()
    
    # 6. Call route again: should STILL return the old name from the cache
    # (Since it doesn't query DB, this proves cache hit)
    resp = client.get("/api/v1/app/cash-register/sales", headers=tenant_headers)
    assert resp.status_code == 200
    
    # 7. Invalidate the cache
    invalidate_tenant_cache(tenant_id, "cachetest")
    
    # Cache should be empty now
    assert cache_service.get(f"dymo:tenant:id:{tenant_id}") is None
    
    # 8. Call route again: should load the fresh name from Postgres
    resp = client.get("/api/v1/app/cash-register/sales", headers=tenant_headers)
    assert resp.status_code == 200
    
    cached_tenant_new = cache_service.get(f"dymo:tenant:id:{tenant_id}")
    assert cached_tenant_new is not None
    assert cached_tenant_new["name"] == "Cache Test Updated Name"


def test_user_permissions_cache_hit_and_invalidation(client, db_session):
    # 1. Login as Platform Admin & Provision Tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    tenant_payload = {
        "name": "Perm Test Inc",
        "slug": "permtest",
        "owner_email": "owner@permtest.com",
        "owner_phone": "+33612345678",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }
    prov_resp = client.post("/api/v1/platform/tenants", json=tenant_payload, headers=headers)
    tenant_id = prov_resp.json()["data"]["id"]
    
    # Subscribe Tenant to Plan
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    sub = Subscription(
        tenant_id=uuid.UUID(tenant_id),
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()
    
    # 2. Get Owner User ID
    owner_user = db_session.query(TenantUser).filter(TenantUser.tenant_id == uuid.UUID(tenant_id), TenantUser.email == "owner@permtest.com").first()
    owner_id = owner_user.id
    
    # 3. Create a non-owner user (standard user)
    standard_user = TenantUser(
        tenant_id=uuid.UUID(tenant_id),
        email="staff@permtest.com",
        phone="+33600000000",
        first_name="Staff",
        last_name="Member",
        password_hash=hash_password("StaffPass123!"),
        status="active"
    )
    db_session.add(standard_user)
    db_session.flush()
    
    # Create standard user role with cash_register_simple.sales.view permission
    user_role = TenantRole(
        tenant_id=uuid.UUID(tenant_id),
        name="billing_staff",
        description="Billing access"
    )
    db_session.add(user_role)
    db_session.flush()
    
    # Link permission to role
    perm = db_session.query(TenantPermission).filter(TenantPermission.code == "cash_register_simple.sales.view").first()
    if not perm:
        perm = TenantPermission(code="cash_register_simple.sales.view", name="View Sales", description="")
        db_session.add(perm)
        db_session.flush()
    user_role.permissions.append(perm)
    
    # Assign role to user
    standard_user.roles.append(user_role)
    db_session.commit()
    
    # 4. Login as standard user
    login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "staff@permtest.com",
        "password": "StaffPass123!"
    }, headers={
        "X-Tenant-Slug": "permtest"
    })
    assert login_resp.status_code == 200
    staff_token = login_resp.json()["data"]["access_token"]
    staff_headers = {
        "Authorization": f"Bearer {staff_token}",
        "X-Tenant-Slug": "permtest"
    }
    
    # 5. Access sales route (requires cash_register_simple.sales.view) -> should succeed
    resp = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp.status_code == 200
    
    # Verify cached permissions
    cache_key = f"dymo:tenant_user_permissions:{tenant_id}:{standard_user.id}"
    cached_perms = cache_service.get(cache_key)
    assert cached_perms is not None
    assert cached_perms["is_owner"] is False
    assert "cash_register_simple.sales.view" in cached_perms["permissions"]
    
    # 6. Direct DB mutation: remove the role from user (bypassing route invalidation)
    db_session.execute(
        tenant_user_roles.delete().where(
            (tenant_user_roles.c.user_id == standard_user.id) &
            (tenant_user_roles.c.role_id == user_role.id)
        )
    )
    db_session.commit()
    
    # 7. Call route again: should STILL succeed because permissions are cached!
    resp = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp.status_code == 200
    
    # 8. Invalidate user permissions cache
    invalidate_user_permissions_cache(tenant_id, standard_user.id)
    assert cache_service.get(cache_key) is None
    
    # 9. Call route again: should now be FORBIDDEN because cache miss reloaded the updated DB roles
    resp = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp.status_code == 403


def test_redis_offline_graceful_fallback(client, db_session):
    # 1. Login as Platform Admin & Provision Tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    tenant_payload = {
        "name": "Fallback Test Inc",
        "slug": "fallbacktest",
        "owner_email": "owner@fallbacktest.com",
        "owner_phone": "+33612345678",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }
    prov_resp = client.post("/api/v1/platform/tenants", json=tenant_payload, headers=headers)
    tenant_id = prov_resp.json()["data"]["id"]
    
    # Subscribe Tenant to Plan
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    sub = Subscription(
        tenant_id=uuid.UUID(tenant_id),
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()
    
    tenant_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@fallbacktest.com",
        "password": "ChangeMe123!"
    }, headers={
        "X-Tenant-Slug": "fallbacktest"
    })
    tenant_token = tenant_login_resp.json()["data"]["access_token"]
    tenant_headers = {
        "Authorization": f"Bearer {tenant_token}",
        "X-Tenant-Slug": "fallbacktest"
    }
    
    # Mock cache_service.get to raise a connection error (simulating Redis down)
    with patch.object(cache_service, "get", side_effect=Exception("Redis Connection Refused")):
        # Request should succeed because it falls back to DB query
        resp = client.get("/api/v1/app/cash-register/sales", headers=tenant_headers)
        assert resp.status_code == 200
