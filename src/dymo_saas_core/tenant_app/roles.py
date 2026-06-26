import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.tenant_context import require_tenant_user
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import AppException, ForbiddenException, NotFoundException
from dymo_saas_core.core.cache_helpers import invalidate_user_permissions_cache
from dymo_saas_core.core.module_registry import is_module_enabled_for_tenant
from dymo_saas_core.models.models import TenantRole, TenantPermission
from dymo_saas_core.tenant_app.schemas import RoleCreateRequest, RoleUpdateRequest, RolePermissionsAssignRequest

router = APIRouter(tags=["Tenant Roles"])

@router.get("/roles")
def list_roles(db: Session = Depends(get_db), current_user = Depends(require_tenant_user)):
    roles = db.query(TenantRole).filter(TenantRole.tenant_id == current_user.tenant_id).all()
    return success_response([
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "permissions": [p.code for p in r.permissions]
        }
        for r in roles
    ])

@router.post("/roles", status_code=201)
def create_role(
    payload: RoleCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    # Check duplicate name
    existing = db.query(TenantRole).filter(
        TenantRole.tenant_id == current_user.tenant_id,
        TenantRole.name == payload.name
    ).first()
    if existing:
        raise AppException("Role name already exists for this tenant", "DUPLICATE_ROLE_NAME", 400)

    role = TenantRole(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    return success_response({
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": []
    })

@router.get("/roles/{role_id}")
def get_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    role = db.query(TenantRole).filter(
        TenantRole.id == role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found")

    return success_response({
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": [p.code for p in role.permissions]
    })

@router.patch("/roles/{role_id}")
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    role = db.query(TenantRole).filter(
        TenantRole.id == role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found")

    if role.name == "owner":
        raise ForbiddenException("The owner role cannot be modified")

    if payload.name is not None:
        # Check duplicate name
        dup = db.query(TenantRole).filter(
            TenantRole.tenant_id == current_user.tenant_id,
            TenantRole.name == payload.name,
            TenantRole.id != role_id
        ).first()
        if dup:
            raise AppException("Role name already exists for this tenant", "DUPLICATE_ROLE_NAME", 400)
        role.name = payload.name

    if payload.description is not None:
        role.description = payload.description

    db.commit()
    db.refresh(role)

    # Invalidate cache for all users of this role
    for u in role.users:
        invalidate_user_permissions_cache(current_user.tenant_id, u.id)

    return success_response({
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": [p.code for p in role.permissions]
    })

@router.delete("/roles/{role_id}")
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    role = db.query(TenantRole).filter(
        TenantRole.id == role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found")

    if role.name == "owner":
        raise ForbiddenException("The owner role cannot be deleted")

    users_to_invalidate = list(role.users)

    db.delete(role)
    db.commit()

    # Invalidate cache for all affected users
    for u in users_to_invalidate:
        invalidate_user_permissions_cache(current_user.tenant_id, u.id)

    return success_response(message="Role deleted successfully")

@router.post("/roles/{role_id}/permissions")
def associate_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsAssignRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    role = db.query(TenantRole).filter(
        TenantRole.id == role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found")

    if role.name == "owner":
        raise ForbiddenException("The owner role permissions cannot be modified")

    # Fetch permissions
    permissions = db.query(TenantPermission).filter(TenantPermission.id.in_(payload.permission_ids)).all()
    if len(permissions) != len(payload.permission_ids):
        raise NotFoundException("One or more permissions not found")

    # Validate module gating
    for perm in permissions:
        if perm.module_key:
            if not is_module_enabled_for_tenant(db, current_user.tenant_id, perm.module_key):
                raise AppException(f"Module '{perm.module_key}' is not enabled for this tenant", "MODULE_NOT_ENABLED", 400)

    # Associate permissions
    for perm in permissions:
        if perm not in role.permissions:
            role.permissions.append(perm)

    db.commit()
    db.refresh(role)

    # Invalidate cache for all users of this role
    for u in role.users:
        invalidate_user_permissions_cache(current_user.tenant_id, u.id)

    return success_response({
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": [p.code for p in role.permissions]
    })

@router.delete("/roles/{role_id}/permissions/{permission_id}")
def remove_permission(
    role_id: uuid.UUID,
    permission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("roles.manage"))
):
    role = db.query(TenantRole).filter(
        TenantRole.id == role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found")

    if role.name == "owner":
        raise ForbiddenException("The owner role permissions cannot be modified")

    perm = next((p for p in role.permissions if p.id == permission_id), None)
    if not perm:
        raise NotFoundException("Permission not associated with this role")

    role.permissions.remove(perm)
    db.commit()
    db.refresh(role)

    # Invalidate cache for all users of this role
    for u in role.users:
        invalidate_user_permissions_cache(current_user.tenant_id, u.id)

    return success_response({
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": [p.code for p in role.permissions]
    })

@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db), current_user = Depends(require_tenant_user)):
    perms = db.query(TenantPermission).all()
    return success_response([
        {
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "module_key": p.module_key
        }
        for p in perms
    ])
