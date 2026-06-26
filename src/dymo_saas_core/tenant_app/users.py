import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.tenant_context import require_tenant_user
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.exceptions import ForbiddenException, NotFoundException, AppException
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.models.models import TenantUser, TenantRole
from dymo_saas_core.tenant_app.schemas import TenantUserCreateRequest, TenantUserUpdateRequest

router = APIRouter(tags=["Tenant Users"])

@router.get("")
def list_users(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    query = db.query(TenantUser).filter(
        TenantUser.tenant_id == current_user.tenant_id,
        TenantUser.deleted_at == None
    ).order_by(TenantUser.created_at.desc())
    
    users, meta = paginate_query(db, query, page, per_page)
    return success_response(
        data=[
            {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "status": u.status,
                "created_at": u.created_at.isoformat()
            }
            for u in users
        ],
        meta=meta
    )

@router.post("")
def create_user(
    body: TenantUserCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    existing = db.query(TenantUser).filter(
        TenantUser.tenant_id == current_user.tenant_id,
        TenantUser.email == body.email,
        TenantUser.deleted_at == None
    ).first()
    if existing:
        raise AppException("Email already exists in this tenant", "EMAIL_EXISTS", 409)
        
    user = TenantUser(
        tenant_id=current_user.tenant_id,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=hash_password(body.password),
        status="active"
    )
    db.add(user)
    db.flush()
    
    if body.role_ids:
        for r_id in body.role_ids:
            role = db.query(TenantRole).filter(
                TenantRole.id == r_id,
                TenantRole.tenant_id == current_user.tenant_id
            ).first()
            if role:
                user.roles.append(role)
                
    db.commit()
    return success_response({
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "status": user.status
    }, message="User created successfully")

@router.get("/{user_id}")
def get_user_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == current_user.tenant_id,
        TenantUser.deleted_at == None
    ).first()
    if not user:
        raise NotFoundException("User not found", "USER_NOT_FOUND")
        
    return success_response({
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "status": user.status,
        "roles": [
            {
                "id": str(role.id),
                "name": role.name,
                "description": role.description
            }
            for role in user.roles
        ],
        "created_at": user.created_at.isoformat()
    })

@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: TenantUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == current_user.tenant_id,
        TenantUser.deleted_at == None
    ).first()
    if not user:
        raise NotFoundException("User not found", "USER_NOT_FOUND")
        
    if body.first_name is not None:
        user.first_name = body.first_name
    if body.last_name is not None:
        user.last_name = body.last_name
    if body.status is not None:
        user.status = body.status
        
    if body.role_ids is not None:
        user.roles.clear()
        for r_id in body.role_ids:
            role = db.query(TenantRole).filter(
                TenantRole.id == r_id,
                TenantRole.tenant_id == current_user.tenant_id
            ).first()
            if role:
                user.roles.append(role)
                
    db.commit()
    
    # Invalidate cache
    try:
        from dymo_saas_core.core.cache_helpers import invalidate_user_permissions_cache
        invalidate_user_permissions_cache(user.tenant_id, user.id)
    except Exception:
        pass
        
    return success_response({
        "id": str(user.id),
        "email": user.email,
        "status": user.status
    }, message="User updated successfully")

@router.delete("/{user_id}")
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == current_user.tenant_id,
        TenantUser.deleted_at == None
    ).first()
    if not user:
        raise NotFoundException("User not found", "USER_NOT_FOUND")
        
    if user.id == current_user.id:
        raise ForbiddenException("You cannot delete your own user account", "DELETE_SELF_PROHIBITED")
        
    user.deleted_at = datetime.now(timezone.utc)
    user.status = "deleted"
    db.commit()
    
    # Invalidate cache
    try:
        from dymo_saas_core.core.cache_helpers import invalidate_user_permissions_cache
        invalidate_user_permissions_cache(user.tenant_id, user.id)
    except Exception:
        pass
        
    return success_response(message="User soft-deleted successfully")
