from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.security import hash_password, hash_token
from dymo_saas_core.core.exceptions import NotFoundException, AppException
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import TenantInvitation, TenantUser, TenantRole

from dymo_saas_core.core.utils import write_audit_log

class AcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=6)
    first_name: str
    last_name: str

tenant_app_router = APIRouter()

from dymo_saas_core.tenant_app.auth import router as auth_router
from dymo_saas_core.tenant_app.users import router as users_router
from dymo_saas_core.tenant_app.invitations import router as invitations_router
from dymo_saas_core.tenant_app.roles import router as roles_router
from dymo_saas_core.tenant_app.billing import router as billing_router
from dymo_saas_core.tenant_app.settings.routes import router as settings_router
from dymo_saas_core.tenant_app.api_keys import router as api_keys_router
from dymo_saas_core.tenant_app.webhooks import router as webhooks_router

tenant_app_router.include_router(auth_router, prefix="/auth")
tenant_app_router.include_router(users_router, prefix="/users")
tenant_app_router.include_router(invitations_router, prefix="/invitations")
tenant_app_router.include_router(roles_router)
tenant_app_router.include_router(billing_router, prefix="/billing")
tenant_app_router.include_router(settings_router, prefix="/settings")
tenant_app_router.include_router(api_keys_router)
tenant_app_router.include_router(webhooks_router)

@tenant_app_router.get("/status")
def get_status():
    return success_response({"status": "healthy", "service": "app"})

@tenant_app_router.post("/invitations/accept")
def accept_invitation(body: AcceptInvitationRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(body.token)
    
    invitation = db.query(TenantInvitation).filter(
        TenantInvitation.token_hash == token_hash,
        TenantInvitation.status == "pending"
    ).first()
    
    if not invitation:
        raise NotFoundException("Invitation not found or already processed", "INVITATION_NOT_FOUND")
        
    if invitation.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        invitation.status = "expired"
        db.commit()
        raise AppException("Invitation has expired", "INVITATION_EXPIRED", 400)
        
    # Check if a user with this email already exists in this tenant (e.g. if created manually meanwhile)
    existing_user = db.query(TenantUser).filter(
        TenantUser.tenant_id == invitation.tenant_id,
        TenantUser.email == invitation.email,
        TenantUser.deleted_at == None
    ).first()
    
    if existing_user:
        # Just assign the role and activate
        user = existing_user
        user.first_name = body.first_name
        user.last_name = body.last_name
        user.password_hash = hash_password(body.password)
        user.status = "active"
    else:
        user = TenantUser(
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            first_name=body.first_name,
            last_name=body.last_name,
            password_hash=hash_password(body.password),
            status="active"
        )
        db.add(user)
        db.flush()
        
    # Assign Role
    role = db.query(TenantRole).filter(TenantRole.id == invitation.role_id).first()
    if role and role not in user.roles:
        user.roles.append(role)
        
    # Update invitation status
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    
    # Write audit log
    write_audit_log(
        db=db,
        tenant_id=invitation.tenant_id,
        user_id=user.id,
        action="tenant.invitation_accepted",
        payload={"email": user.email, "role": role.name if role else None}
    )
    
    db.commit()
    return success_response({
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email
    }, message="Invitation accepted successfully. You can now login.")

