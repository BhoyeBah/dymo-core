import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.security import decode_token, coerce_uuid
from dymo_saas_core.core.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    TenantSuspendedException
)

security_scheme = HTTPBearer(auto_error=False)

class ApiKeyUserContext:
    def __init__(self, key_id: uuid.UUID, tenant_id: uuid.UUID, scopes: list, email: str = "api_key@dymo.com"):
        self.id = key_id
        self.tenant_id = tenant_id
        self.scopes = scopes
        self.email = email
        self.is_api_key = True

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: Session = Depends(get_db)
) -> Any:
    from dymo_saas_core.models.models import TenantUser, TenantApiKey, Tenant
    
    # 1. Check for API key in headers/X-API-Key/Authorization: ApiKey
    api_key_val = None
    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("X-API-Key")
    
    if api_key_header:
        api_key_val = api_key_header
    elif auth_header and auth_header.startswith("ApiKey "):
        api_key_val = auth_header[7:].strip()
        
    if api_key_val:
        parts = api_key_val.split("_", 3)
        if len(parts) != 4 or parts[0] != "dymo" or parts[1] != "sk":
            raise UnauthorizedException("Invalid API key format", "INVALID_API_KEY_FORMAT")
            
        prefix = parts[2]
        
        # Query API Key by prefix
        api_key = db.query(TenantApiKey).filter(
            TenantApiKey.key_prefix == prefix
        ).first()
        
        if not api_key:
            raise UnauthorizedException("Invalid API key", "INVALID_API_KEY")
            
        # Verify key hash
        hashed_input = hashlib.sha256(api_key_val.encode()).hexdigest()
        if hashed_input != api_key.key_hash:
            raise UnauthorizedException("Invalid API key", "INVALID_API_KEY")
            
        # Verify key status
        if api_key.status != "active":
            raise ForbiddenException(f"API key is {api_key.status}", "API_KEY_INACTIVE")
            
        # Verify expiration
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            api_key.status = "expired"
            db.commit()
            raise ForbiddenException("API key has expired", "API_KEY_EXPIRED")
            
        # Verify tenant status
        tenant = db.query(Tenant).filter(Tenant.id == coerce_uuid(api_key.tenant_id)).first()
        if not tenant:
            raise UnauthorizedException("Tenant not found", "TENANT_NOT_FOUND")
        if tenant.status == "deleted":
            raise ForbiddenException("Tenant has been deleted", "TENANT_DELETED")
        if tenant.status == "suspended":
            raise TenantSuspendedException("Tenant account is suspended", "TENANT_SUSPENDED")
        if tenant.status not in ["active", "trial"]:
            raise ForbiddenException(f"Tenant account status is {tenant.status}", "TENANT_NOT_ACTIVE")
            
        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        
        # Set request state for logging middleware
        request.state.api_key_id = api_key.id
        request.state.tenant_id = api_key.tenant_id
        
        # Return virtual API Key user context
        return ApiKeyUserContext(
            key_id=api_key.id,
            tenant_id=api_key.tenant_id,
            scopes=api_key.scopes or [],
            email="api_key@dymo.com"
        )
        
    # 2. Fallback to standard Bearer JWT token
    if not credentials:
        raise UnauthorizedException("Not authenticated", "NOT_AUTHENTICATED")
        
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload.get("user_type") != "tenant_user":
        raise ForbiddenException("Access denied: tenant user account required", "TENANT_USER_REQUIRED")
        
    user_id = coerce_uuid(payload.get("user_id"))
    tenant_id = coerce_uuid(payload.get("tenant_id"))
    if not user_id or not tenant_id:
        raise UnauthorizedException("Invalid token payload", "INVALID_PAYLOAD")
        
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise UnauthorizedException("Tenant user not found", "USER_NOT_FOUND")
        
    if user.status != "active":
        raise ForbiddenException(f"User account status is {user.status}", "USER_INACTIVE")
        
    return user

def require_tenant_user(
    user = Depends(get_current_user)
) -> Any:
    return user

def get_current_tenant(
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    from dymo_saas_core.models.models import Tenant
    from dymo_saas_core.core.cache import cache_service
    import uuid
    from datetime import datetime
    
    tenant_id = user.tenant_id
    cache_key = f"dymo:tenant:id:{tenant_id}"
    tenant_dict = None
    
    try:
        tenant_dict = cache_service.get(cache_key)
    except Exception:
        pass
        
    if tenant_dict and isinstance(tenant_dict, dict):
        suspended_at = datetime.fromisoformat(tenant_dict["suspended_at"]) if tenant_dict.get("suspended_at") else None
        cancelled_at = datetime.fromisoformat(tenant_dict["cancelled_at"]) if tenant_dict.get("cancelled_at") else None
        deleted_at = datetime.fromisoformat(tenant_dict["deleted_at"]) if tenant_dict.get("deleted_at") else None
        
        tenant = Tenant(
            id=uuid.UUID(tenant_dict["id"]) if isinstance(tenant_dict["id"], str) else tenant_dict["id"],
            name=tenant_dict.get("name"),
            slug=tenant_dict.get("slug"),
            status=tenant_dict.get("status"),
            owner_email=tenant_dict.get("owner_email"),
            owner_phone=tenant_dict.get("owner_phone"),
            country=tenant_dict.get("country"),
            currency=tenant_dict.get("currency"),
            timezone=tenant_dict.get("timezone"),
            language=tenant_dict.get("language"),
            suspended_at=suspended_at,
            cancelled_at=cancelled_at,
            deleted_at=deleted_at
        )
    else:
        tenant = db.query(Tenant).filter(Tenant.id == coerce_uuid(tenant_id)).first()
        if not tenant:
            raise UnauthorizedException("Tenant not found", "TENANT_NOT_FOUND")
            
        tenant_dict = {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "owner_email": tenant.owner_email,
            "owner_phone": tenant.owner_phone,
            "country": tenant.country,
            "currency": tenant.currency,
            "timezone": tenant.timezone,
            "language": tenant.language,
            "suspended_at": tenant.suspended_at.isoformat() if tenant.suspended_at else None,
            "cancelled_at": tenant.cancelled_at.isoformat() if tenant.cancelled_at else None,
            "deleted_at": tenant.deleted_at.isoformat() if tenant.deleted_at else None,
        }
        try:
            cache_service.set(cache_key, tenant_dict, ttl=300)
        except Exception:
            pass
            
    if tenant.status == "deleted":
        raise ForbiddenException("Tenant has been deleted", "TENANT_DELETED")
        
    return tenant


def require_active_tenant(
    tenant = Depends(get_current_tenant)
) -> Any:
    if tenant.status == "suspended":
        raise TenantSuspendedException("Tenant account is suspended", "TENANT_SUSPENDED")
    if tenant.status not in ["active", "trial"]:
        raise ForbiddenException(f"Tenant account status is {tenant.status}", "TENANT_NOT_ACTIVE")
    return tenant
