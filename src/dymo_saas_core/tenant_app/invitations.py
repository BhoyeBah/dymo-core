from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import NotFoundException, AppException
from dymo_saas_core.core.security import generate_secure_token, hash_token
from dymo_saas_core.models.models import TenantInvitation, TenantRole
from dymo_saas_core.tenant_app.schemas import TenantInvitationCreateRequest
from dymo_saas_core.core.idempotency import require_idempotency, mark_idempotency_completed

router = APIRouter(tags=["Tenant Invitations"])

@router.get("")
def list_invitations(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    invitations = db.query(TenantInvitation).filter(
        TenantInvitation.tenant_id == current_user.tenant_id
    ).all()
    return success_response([
        {
            "id": str(i.id),
            "email": i.email,
            "phone": i.phone,
            "role_id": str(i.role_id),
            "status": i.status,
            "expires_at": i.expires_at.isoformat(),
            "created_at": i.created_at.isoformat()
        }
        for i in invitations
    ])

@router.post("")
def create_invitation(
    body: TenantInvitationCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage")),
    idempotency_key: str = Depends(require_idempotency)
):
    role = db.query(TenantRole).filter(
        TenantRole.id == body.role_id,
        TenantRole.tenant_id == current_user.tenant_id
    ).first()
    if not role:
        raise NotFoundException("Role not found in this tenant", "ROLE_NOT_FOUND")
        
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    
    invitation = TenantInvitation(
        tenant_id=current_user.tenant_id,
        email=body.email,
        role_id=body.role_id,
        invited_by_user_id=current_user.id,
        token_hash=token_hash,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2)
    )
    db.add(invitation)
    db.commit()
    
    mark_idempotency_completed(
        db, 
        idempotency_key, 
        f"POST:/api/v1/app/invitations", 
        200, 
        f"Invitation created: {invitation.id}"
    )
    
    return success_response({
        "id": str(invitation.id),
        "email": invitation.email,
        "token": raw_token,
        "expires_at": invitation.expires_at.isoformat()
    }, message="Invitation created successfully")

@router.post("/{invitation_id}/revoke")
def revoke_invitation(
    invitation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("users.manage"))
):
    invitation = db.query(TenantInvitation).filter(
        TenantInvitation.id == invitation_id,
        TenantInvitation.tenant_id == current_user.tenant_id
    ).first()
    if not invitation:
        raise NotFoundException("Invitation not found", "INVITATION_NOT_FOUND")
        
    if invitation.status != "pending":
        raise AppException(f"Cannot revoke invitation in status: {invitation.status}", "INVALID_STATUS")
        
    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return success_response(message="Invitation revoked successfully")
