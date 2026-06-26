import pytest
import uuid
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from dymo_saas_core.core.cache import cache_service
from dymo_saas_core.core.module_registry import is_module_enabled_for_tenant
from dymo_saas_core.core.storage import (
    LocalStorageProvider, S3StorageProvider, get_storage_service
)
from dymo_saas_core.jobs.cleanup import (
    cleanup_expired_idempotency_keys, cleanup_expired_invitations
)
from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanModule, Subscription,
    Tenant, TenantModule, IdempotencyKey, TenantInvitation, TenantRole
)
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.core.module_registry import sync_modules_to_database
from dymo_saas_core.cli import cli

@pytest.fixture(autouse=True)
def seed_test_data(db_session):
    """Seed base data required for testing."""
    # Seed platform admin
    admin = PlatformAdmin(
        email="admin@dymo.com",
        password_hash=hash_password("DymoAdmin2026!"),
        first_name="Super",
        last_name="Admin",
        is_active=True
    )
    db_session.add(admin)
    
    # Sync available modules
    sync_modules_to_database(db_session)
    
    # Seed Plan
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


def test_module_gating_caching_and_event_invalidation(db_session):
    # Create a real Tenant first to satisfy foreign key constraints
    tenant = Tenant(name="Test Tenant A", slug="test-tenant-a", owner_email="owner-a@test.com")
    db_session.add(tenant)
    db_session.flush()
    tenant_id = tenant.id

    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    
    # 1. Create active subscription -> standard plan has cash_register_simple enabled
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
    
    # 2. Check enabled modules (should load and cache)
    assert is_module_enabled_for_tenant(db_session, tenant_id, "cash_register_simple") is True
    
    # Verify cached list
    cache_key = f"dymo:tenant_modules:{tenant_id}"
    cached_modules = cache_service.get(cache_key)
    assert cached_modules is not None
    assert "cash_register_simple" in cached_modules
    
    # 3. Add override TenantModule (disabled cash_register_simple)
    tm = TenantModule(
        tenant_id=tenant_id,
        module_key="cash_register_simple",
        is_enabled=False
    )
    db_session.add(tm)
    db_session.commit() # This should trigger the database event listener to delete cache
    
    # 4. Cache should have been invalidated automatically
    assert cache_service.get(cache_key) is None
    
    # 5. Check enabled modules again -> should query DB, find the override, cache it, and return False
    assert is_module_enabled_for_tenant(db_session, tenant_id, "cash_register_simple") is False
    assert "cash_register_simple" not in cache_service.get(cache_key)


def test_local_storage_provider():
    # Setup temporary local upload path in workspace
    temp_dir = "storage/test_uploads"
    provider = LocalStorageProvider(base_dir=temp_dir)
    
    file_name = "test_doc.txt"
    file_content = b"Dymo SaaS Core storage test file content."
    
    # Upload file
    file_url = provider.upload_file(file_name, file_content, content_type="text/plain")
    assert file_url is not None
    assert file_name in file_url
    assert os.path.exists(file_url)
    
    # Verify content
    read_content = Path(file_url).read_bytes()
    assert read_content == file_content
    
    # Delete file
    deleted = provider.delete_file(file_url)
    assert deleted is True
    assert not os.path.exists(file_url)
    
    # Clean up directory
    if os.path.exists(temp_dir):
        import shutil
        shutil.rmtree(temp_dir)


def test_storage_service_config_and_fallback():
    # Test fallback when s3 is selected but credentials/bucket are missing
    with patch("dymo_saas_core.core.config.settings.STORAGE_PROVIDER", "s3"), \
         patch("dymo_saas_core.core.config.settings.S3_BUCKET_NAME", ""), \
         patch("dymo_saas_core.core.config.settings.S3_ACCESS_KEY_ID", ""):
        service = get_storage_service()
        assert isinstance(service, LocalStorageProvider)

    # Test LocalStorageProvider choice when selected
    with patch("dymo_saas_core.core.config.settings.STORAGE_PROVIDER", "local"):
        service = get_storage_service()
        assert isinstance(service, LocalStorageProvider)


def test_cleanup_expired_idempotency_keys(db_session):
    # Create non-expired key
    valid_key = IdempotencyKey(
        scope="tenant:123",
        key="valid-key-123",
        request_hash="abc",
        response_body="{}",
        status_code=200,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    # Create expired key
    expired_key = IdempotencyKey(
        scope="tenant:123",
        key="expired-key-456",
        request_hash="def",
        response_body="{}",
        status_code=200,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    
    db_session.add_all([valid_key, expired_key])
    db_session.commit()
    
    # Run cleanup
    deleted = cleanup_expired_idempotency_keys(db_session)
    assert deleted == 1
    
    # Verify remaining keys
    remaining = db_session.query(IdempotencyKey).filter(IdempotencyKey.scope == "tenant:123").all()
    assert len(remaining) == 1
    assert remaining[0].key == "valid-key-123"


def test_cleanup_expired_invitations(db_session):
    # Create a real Tenant first to satisfy foreign key constraints
    tenant = Tenant(name="Test Tenant B", slug="test-tenant-b", owner_email="owner-b@test.com")
    db_session.add(tenant)
    db_session.flush()
    tenant_id = tenant.id
    
    # Create a role for reference
    role = TenantRole(tenant_id=tenant_id, name="staff", description="")
    db_session.add(role)
    db_session.flush()
    
    # Create valid pending invitation
    valid_inv = TenantInvitation(
        tenant_id=tenant_id,
        email="valid@dymo.com",
        role_id=role.id,
        token_hash="hash1",
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2)
    )
    # Create expired pending invitation
    expired_inv = TenantInvitation(
        tenant_id=tenant_id,
        email="expired@dymo.com",
        role_id=role.id,
        token_hash="hash2",
        status="pending",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    # Create expired but accepted invitation
    accepted_inv = TenantInvitation(
        tenant_id=tenant_id,
        email="accepted@dymo.com",
        role_id=role.id,
        token_hash="hash3",
        status="accepted",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    
    db_session.add_all([valid_inv, expired_inv, accepted_inv])
    db_session.commit()
    
    # Run cleanup
    deleted = cleanup_expired_invitations(db_session)
    assert deleted == 1
    
    # Verify remaining
    remaining = db_session.query(TenantInvitation).filter(TenantInvitation.tenant_id == tenant_id).all()
    remaining_emails = {inv.email for inv in remaining}
    assert "valid@dymo.com" in remaining_emails
    assert "accepted@dymo.com" in remaining_emails
    assert "expired@dymo.com" not in remaining_emails


def test_cli_cleanup_jobs(db_session):
    # Add an expired key to be deleted
    expired_key = IdempotencyKey(
        scope="tenant:cli",
        key="cli-expired",
        request_hash="xyz",
        response_body="",
        status_code=200,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=5)
    )
    db_session.add(expired_key)
    db_session.commit()
    
    runner = CliRunner()
    result = runner.invoke(cli, ["cleanup-jobs"])
    assert result.exit_code == 0
    assert "Cleanup completed" in result.output
    
    # Verify it was cleaned up
    remaining = db_session.query(IdempotencyKey).filter(IdempotencyKey.key == "cli-expired").first()
    assert remaining is None


def test_sentry_initialization():
    with patch("dymo_saas_core.core.config.settings.SENTRY_DSN", "https://mock@sentry.io/123"), \
         patch("sentry_sdk.init") as mock_sentry_init:
        from dymo_saas_core.core.observability import setup_sentry
        setup_sentry()
        mock_sentry_init.assert_called()
