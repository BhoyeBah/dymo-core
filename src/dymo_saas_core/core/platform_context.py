from typing import Any
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.security import decode_token, coerce_uuid
from dymo_saas_core.core.exceptions import UnauthorizedException, ForbiddenException

security_scheme = HTTPBearer()

def require_platform_admin(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    db: Session = Depends(get_db)
) -> Any:
    # We use Any for the return type here because PlatformAdmin is imported dynamically inside to avoid circular imports.
    # We will resolve the actual model class inside the function.
    from dymo_saas_core.models.models import PlatformAdmin
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload.get("user_type") != "platform_admin":
        raise ForbiddenException("Access denied: platform administrator account required", "PLATFORM_ADMIN_REQUIRED")
        
    admin_id = coerce_uuid(payload.get("admin_id"))
    if not admin_id:
        raise UnauthorizedException("Invalid token payload", "INVALID_PAYLOAD")
        
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == coerce_uuid(admin_id)).first()
    if not admin:
        raise UnauthorizedException("Platform administrator not found", "ADMIN_NOT_FOUND")
        
    if not admin.is_active:
        raise ForbiddenException("Platform administrator account is disabled", "ADMIN_DISABLED")
        
    return admin

def require_platform_permission(permission_code: str):
    def dependency(
        admin = Depends(require_platform_admin),
        db: Session = Depends(get_db)
    ):
        from dymo_saas_core.models.models import PlatformPermission, platform_role_permissions, platform_admin_roles
        
        has_permission = db.query(PlatformPermission).join(
            platform_role_permissions, platform_role_permissions.c.permission_id == PlatformPermission.id
        ).join(
            platform_admin_roles, platform_admin_roles.c.role_id == platform_role_permissions.c.role_id
        ).filter(
            platform_admin_roles.c.admin_id == admin.id,
            PlatformPermission.code == permission_code
        ).first() is not None
        
        if not has_permission:
            raise ForbiddenException(f"Missing platform permission: {permission_code}", "PERMISSION_DENIED")
            
        return admin
    return dependency
