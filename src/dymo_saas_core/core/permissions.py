from fastapi import Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.tenant_context import require_tenant_user, require_active_tenant
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.exceptions import ForbiddenException, QuotaExceededException

def require_authenticated_user(user = Depends(require_tenant_user)):
    """
    Returns the authenticated tenant user context.
    """
    return user

def require_super_admin(admin = Depends(require_platform_admin)):
    """
    Returns the authenticated platform admin context.
    """
    return admin

def require_tenant_member(
    user = Depends(require_tenant_user),
    tenant = Depends(require_active_tenant)
):
    """
    Verifies that the user is authenticated and the tenant is active.
    """
    return user

def require_role(role_name: str):
    """
    Verifies if the tenant user has the specified role.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import TenantRole, tenant_user_roles
        
        is_owner = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name == "owner"
        ).first() is not None
        
        if is_owner:
            return user
            
        has_role = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name == role_name
        ).first() is not None
        
        if not has_role:
            raise ForbiddenException(f"Role '{role_name}' required", "ROLE_DENIED")
        return user
    return dependency

def require_any_role(role_names: list[str]):
    """
    Verifies if the tenant user has any of the specified roles.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import TenantRole, tenant_user_roles
        
        is_owner = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name == "owner"
        ).first() is not None
        
        if is_owner:
            return user
            
        has_role = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name.in_(role_names)
        ).first() is not None
        
        if not has_role:
            raise ForbiddenException(f"One of the roles {role_names} required", "ROLE_DENIED")
        return user
    return dependency

def require_permission(permission_code: str):
    """
    FastAPI dependency to verify if the current tenant user has the specified RBAC permission.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import TenantPermission, TenantRole, tenant_role_permissions, tenant_user_roles
        from dymo_saas_core.core.cache import cache_service
        
        # If authenticated via API Key, bypass user RBAC check and validate scope directly
        if getattr(user, "is_api_key", False):
            if permission_code not in getattr(user, "scopes", []):
                raise ForbiddenException(f"Missing required permission: {permission_code}", "PERMISSION_DENIED")
            return user

        tenant_id = user.tenant_id
        user_id = user.id
        cache_key = f"dymo:tenant_user_permissions:{tenant_id}:{user_id}"
        
        cached_data = None
        try:
            cached_data = cache_service.get(cache_key)
        except Exception:
            pass
            
        if cached_data and isinstance(cached_data, dict):
            is_owner = cached_data.get("is_owner", False)
            permissions = cached_data.get("permissions", [])
        else:
            # 1. Check if the user has the 'owner' role (super-administrator of the tenant)
            is_owner = db.query(TenantRole).join(
                tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
            ).filter(
                tenant_user_roles.c.user_id == user_id,
                TenantRole.name == "owner"
            ).first() is not None
            
            permissions = []
            if not is_owner:
                perms = db.query(TenantPermission.code).join(
                    tenant_role_permissions, tenant_role_permissions.c.permission_id == TenantPermission.id
                ).join(
                    tenant_user_roles, tenant_user_roles.c.role_id == tenant_role_permissions.c.role_id
                ).filter(
                    tenant_user_roles.c.user_id == user_id
                ).all()
                permissions = [p[0] for p in perms]
                
            cached_data = {
                "is_owner": is_owner,
                "permissions": permissions
            }
            try:
                cache_service.set(cache_key, cached_data, ttl=120)
            except Exception:
                pass
                
        if is_owner:
            return user
            
        if permission_code not in permissions:
            raise ForbiddenException(f"Missing required permission: {permission_code}", "PERMISSION_DENIED")
            
        return user

    return dependency

def require_any_permission(permission_codes: list[str]):
    """
    Verifies if the tenant user has any of the specified permissions.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import TenantPermission, TenantRole, tenant_role_permissions, tenant_user_roles
        
        if getattr(user, "is_api_key", False):
            if not any(code in getattr(user, "scopes", []) for code in permission_codes):
                raise ForbiddenException(f"Missing one of the permissions: {permission_codes}", "PERMISSION_DENIED")
            return user
            
        is_owner = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name == "owner"
        ).first() is not None
        
        if is_owner:
            return user
            
        has_perm = db.query(TenantPermission.code).join(
            tenant_role_permissions, tenant_role_permissions.c.permission_id == TenantPermission.id
        ).join(
            tenant_user_roles, tenant_user_roles.c.role_id == tenant_role_permissions.c.role_id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantPermission.code.in_(permission_codes)
        ).first() is not None
        
        if not has_perm:
            raise ForbiddenException(f"Missing one of the permissions: {permission_codes}", "PERMISSION_DENIED")
        return user
    return dependency

def require_all_permissions(permission_codes: list[str]):
    """
    Verifies if the tenant user has all of the specified permissions.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import TenantPermission, TenantRole, tenant_role_permissions, tenant_user_roles
        
        if getattr(user, "is_api_key", False):
            if not all(code in getattr(user, "scopes", []) for code in permission_codes):
                raise ForbiddenException(f"Missing all of the permissions: {permission_codes}", "PERMISSION_DENIED")
            return user
            
        is_owner = db.query(TenantRole).join(
            tenant_user_roles, tenant_user_roles.c.role_id == TenantRole.id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantRole.name == "owner"
        ).first() is not None
        
        if is_owner:
            return user
            
        perms = db.query(TenantPermission.code).join(
            tenant_role_permissions, tenant_role_permissions.c.permission_id == TenantPermission.id
        ).join(
            tenant_user_roles, tenant_user_roles.c.role_id == tenant_role_permissions.c.role_id
        ).filter(
            tenant_user_roles.c.user_id == user.id,
            TenantPermission.code.in_(permission_codes)
        ).all()
        
        user_perms = {p[0] for p in perms}
        if not all(code in user_perms for code in permission_codes):
            raise ForbiddenException(f"Missing permissions: {permission_codes}", "PERMISSION_DENIED")
        return user
    return dependency

def require_active_subscription():
    """
    Verifies if the tenant has an active subscription.
    """
    def dependency(
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import Subscription
        sub = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id,
            Subscription.status.in_(["active", "trialing"])
        ).first()
        if not sub:
            raise ForbiddenException("Active subscription required", "NO_ACTIVE_SUBSCRIPTION")
        return sub
    return dependency

def require_feature_access(feature_code: str):
    """
    Verifies if the tenant's current plan includes the feature with the specified code.
    """
    def dependency(
        sub = Depends(require_active_subscription()),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import PlanFeature
        feature = db.query(PlanFeature).filter(
            PlanFeature.plan_id == sub.plan_id,
            PlanFeature.feature_key == feature_code
        ).first()
        if not feature:
            raise ForbiddenException(f"Feature '{feature_code}' not enabled in subscription plan", "FEATURE_ACCESS_DENIED")
        return feature
    return dependency

def require_usage_limit(resource_code: str):
    """
    Verifies if the tenant has not exceeded their quota for the specified resource.
    """
    def dependency(
        sub = Depends(require_active_subscription()),
        user = Depends(require_tenant_user),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import PlanLimit, UsageCounter
        limit = db.query(PlanLimit).filter(
            PlanLimit.plan_id == sub.plan_id,
            PlanLimit.metric_key == resource_code
        ).first()
        if limit:
            counter = db.query(UsageCounter).filter(
                UsageCounter.tenant_id == user.tenant_id,
                UsageCounter.metric_key == resource_code
            ).order_by(UsageCounter.created_at.desc()).first()
            current_value = counter.current_value if counter else 0
            if current_value >= limit.limit_value and not limit.overage_allowed:
                raise QuotaExceededException(f"Usage limit reached for resource: {resource_code}", "QUOTA_EXCEEDED")
        return limit
    return dependency
