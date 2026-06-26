import pytest
import uuid
from datetime import datetime, timezone, timedelta
from dymo_saas_core.core.cache import cache_service
from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanModule, Subscription,
    Tenant, TenantUser, TenantRole, TenantPermission
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

@pytest.fixture
def provisioned_tenant(client, db_session):
    # 1. Platform Admin Login
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Provision Tenant
    tenant_payload = {
        "name": "Dynamic Roles Inc",
        "slug": "rolesdynamic",
        "owner_email": "owner@rolesdynamic.com",
        "owner_phone": "+33612345678",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }
    prov_resp = client.post("/api/v1/platform/tenants", json=tenant_payload, headers=admin_headers)
    tenant_id = uuid.UUID(prov_resp.json()["data"]["id"])
    
    # 3. Subscribe to plan
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    sub = Subscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()
    
    # 4. Login as Owner
    owner_login = client.post("/api/v1/app/auth/login", json={
        "email": "owner@rolesdynamic.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "rolesdynamic"})
    owner_token = owner_login.json()["data"]["access_token"]
    
    # 5. Create a standard staff user
    staff_user = TenantUser(
        tenant_id=tenant_id,
        email="staff@rolesdynamic.com",
        phone="+33611111111",
        first_name="Staff",
        last_name="Member",
        password_hash=hash_password("StaffPass123!"),
        status="active"
    )
    db_session.add(staff_user)
    db_session.flush()
    
    db_session.commit()
    
    # Login as Staff
    staff_login = client.post("/api/v1/app/auth/login", json={
        "email": "staff@rolesdynamic.com",
        "password": "StaffPass123!"
    }, headers={"X-Tenant-Slug": "rolesdynamic"})
    staff_token = staff_login.json()["data"]["access_token"]
    
    return {
        "tenant_id": tenant_id,
        "owner_token": owner_token,
        "staff_token": staff_token,
        "staff_user_id": staff_user.id
    }

def test_roles_crud(client, provisioned_tenant, db_session):
    headers = {
        "Authorization": f"Bearer {provisioned_tenant['owner_token']}",
        "X-Tenant-Slug": "rolesdynamic"
    }
    
    # 1. Create a custom role
    create_resp = client.post("/api/v1/app/roles", json={
        "name": "manager",
        "description": "Store manager"
    }, headers=headers)
    assert create_resp.status_code == 201
    role_data = create_resp.json()["data"]
    assert role_data["name"] == "manager"
    assert role_data["description"] == "Store manager"
    role_id = role_data["id"]
    
    # 2. Get role details
    get_resp = client.get(f"/api/v1/app/roles/{role_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "manager"
    
    # 3. Create duplicate name -> should fail with 400
    dup_resp = client.post("/api/v1/app/roles", json={
        "name": "manager",
        "description": "Another manager"
    }, headers=headers)
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["message"]
    
    # 4. Update the role
    patch_resp = client.patch(f"/api/v1/app/roles/{role_id}", json={
        "name": "lead_manager",
        "description": "Senior manager"
    }, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["name"] == "lead_manager"
    assert patch_resp.json()["data"]["description"] == "Senior manager"
    
    # 5. Delete the role
    del_resp = client.delete(f"/api/v1/app/roles/{role_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Role deleted successfully"
    
    # 6. Verify role is deleted (GET -> 404)
    get_resp2 = client.get(f"/api/v1/app/roles/{role_id}", headers=headers)
    assert get_resp2.status_code == 404

def test_owner_role_guards(client, provisioned_tenant, db_session):
    headers = {
        "Authorization": f"Bearer {provisioned_tenant['owner_token']}",
        "X-Tenant-Slug": "rolesdynamic"
    }
    
    # Find the owner role
    owner_role = db_session.query(TenantRole).filter(
        TenantRole.tenant_id == provisioned_tenant["tenant_id"],
        TenantRole.name == "owner"
    ).first()
    assert owner_role is not None
    owner_role_id = str(owner_role.id)
    
    # 1. Try to update owner role name -> 403
    upd_resp = client.patch(f"/api/v1/app/roles/{owner_role_id}", json={
        "name": "new_owner"
    }, headers=headers)
    assert upd_resp.status_code == 403
    assert "owner role cannot be modified" in upd_resp.json()["message"]
    
    # 2. Try to delete owner role -> 403
    del_resp = client.delete(f"/api/v1/app/roles/{owner_role_id}", headers=headers)
    assert del_resp.status_code == 403
    assert "owner role cannot be deleted" in del_resp.json()["message"]
    
    # 3. Try to modify owner permissions -> 403
    perm = db_session.query(TenantPermission).first()
    perm_id = str(perm.id)
    
    assoc_resp = client.post(f"/api/v1/app/roles/{owner_role_id}/permissions", json={
        "permission_ids": [perm_id]
    }, headers=headers)
    assert assoc_resp.status_code == 403
    assert "owner role permissions cannot be modified" in assoc_resp.json()["message"]
    
    rem_resp = client.delete(f"/api/v1/app/roles/{owner_role_id}/permissions/{perm_id}", headers=headers)
    assert rem_resp.status_code == 403
    assert "owner role permissions cannot be modified" in rem_resp.json()["message"]

def test_role_permissions_association_and_gating(client, provisioned_tenant, db_session):
    headers = {
        "Authorization": f"Bearer {provisioned_tenant['owner_token']}",
        "X-Tenant-Slug": "rolesdynamic"
    }
    
    # Create custom role
    create_resp = client.post("/api/v1/app/roles", json={
        "name": "sales",
        "description": "Sales agent"
    }, headers=headers)
    role_id = create_resp.json()["data"]["id"]
    
    # Get active/enabled permission: billing.view
    billing_perm = db_session.query(TenantPermission).filter(TenantPermission.code == "billing.view").first()
    assert billing_perm is not None
    
    # Get disabled permission (using a non-existent module key)
    dummy_perm = TenantPermission(
        code="dummy.disabled",
        name="Dummy Disabled",
        description="",
        module_key="non_existent_module"
    )
    db_session.add(dummy_perm)
    db_session.commit()
    
    # 1. Associate valid permission -> 200 OK
    assoc_resp = client.post(f"/api/v1/app/roles/{role_id}/permissions", json={
        "permission_ids": [str(billing_perm.id)]
    }, headers=headers)
    assert assoc_resp.status_code == 200
    assert "billing.view" in assoc_resp.json()["data"]["permissions"]
    
    # 2. Attempt to associate gated/disabled permission -> 400 Bad Request
    gated_resp = client.post(f"/api/v1/app/roles/{role_id}/permissions", json={
        "permission_ids": [str(dummy_perm.id)]
    }, headers=headers)
    assert gated_resp.status_code == 400
    assert "not enabled" in gated_resp.json()["message"]
    
    # 3. Remove permission -> 200 OK
    rem_resp = client.delete(f"/api/v1/app/roles/{role_id}/permissions/{billing_perm.id}", headers=headers)
    assert rem_resp.status_code == 200
    assert "billing.view" not in rem_resp.json()["data"]["permissions"]
    
    # 4. Remove permission not associated -> 404
    rem_resp2 = client.delete(f"/api/v1/app/roles/{role_id}/permissions/{billing_perm.id}", headers=headers)
    assert rem_resp2.status_code == 404

def test_roles_cache_invalidation(client, provisioned_tenant, db_session):
    owner_headers = {
        "Authorization": f"Bearer {provisioned_tenant['owner_token']}",
        "X-Tenant-Slug": "rolesdynamic"
    }
    staff_headers = {
        "Authorization": f"Bearer {provisioned_tenant['staff_token']}",
        "X-Tenant-Slug": "rolesdynamic"
    }
    
    # 1. Create a custom role
    create_resp = client.post("/api/v1/app/roles", json={
        "name": "staff_role",
        "description": "Staff role description"
    }, headers=owner_headers)
    role_id = create_resp.json()["data"]["id"]
    
    # Assign the role to the staff user
    staff_user = db_session.query(TenantUser).filter(TenantUser.id == provisioned_tenant["staff_user_id"]).first()
    custom_role = db_session.query(TenantRole).filter(TenantRole.id == uuid.UUID(role_id)).first()
    staff_user.roles.append(custom_role)
    db_session.commit()
    
    # Flush Redis cache
    cache_service.flush()
    
    # 2. Access sales route (requires cash_register_simple.sales.view) -> 403
    resp_init = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp_init.status_code == 403
    
    # User permissions should now be cached
    cache_key = f"dymo:tenant_user_permissions:{provisioned_tenant['tenant_id']}:{provisioned_tenant['staff_user_id']}"
    assert cache_service.get(cache_key) is not None
    
    # 3. Associate cash_register_simple.sales.view to staff_role -> must invalidate cache
    view_perm = db_session.query(TenantPermission).filter(TenantPermission.code == "cash_register_simple.sales.view").first()
    assert view_perm is not None
    
    assoc_resp = client.post(f"/api/v1/app/roles/{role_id}/permissions", json={
        "permission_ids": [str(view_perm.id)]
    }, headers=owner_headers)
    assert assoc_resp.status_code == 200
    
    # Verify cache is invalidated
    assert cache_service.get(cache_key) is None
    
    # 4. Access route again -> 200 OK
    resp_ok = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp_ok.status_code == 200
    assert cache_service.get(cache_key) is not None
    
    # 5. Remove permission -> must invalidate cache
    rem_resp = client.delete(f"/api/v1/app/roles/{role_id}/permissions/{view_perm.id}", headers=owner_headers)
    assert rem_resp.status_code == 200
    
    # Verify cache is invalidated
    assert cache_service.get(cache_key) is None
    
    # 6. Access route again -> 403
    resp_fail = client.get("/api/v1/app/cash-register/sales", headers=staff_headers)
    assert resp_fail.status_code == 403
