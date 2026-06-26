import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.exceptions import AppException, NotFoundException
from dymo_saas_core.models.models import (
    Tenant, TenantProfile, TenantUser, TenantRole, TenantPermission, TenantStatusHistory
)
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.platform.schemas import TenantCreateRequest, TenantUpdateRequest

router = APIRouter(tags=["Platform Tenants"])

@router.get("")
def list_tenants(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin)
):
    query = db.query(Tenant).order_by(Tenant.created_at.desc())
    tenants, meta = paginate_query(db, query, page, per_page)
    return success_response(
        data=[
            {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "status": t.status,
                "owner_email": t.owner_email,
                "owner_phone": t.owner_phone,
                "country": t.country,
                "currency": t.currency,
                "timezone": t.timezone,
                "language": t.language,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat()
            }
            for t in tenants
        ],
        meta=meta
    )

@router.post("")
def create_tenant(
    body: TenantCreateRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin)
):
    # Check if slug already exists
    if db.query(Tenant).filter(Tenant.slug == body.slug).first():
        raise AppException(f"Tenant slug '{body.slug}' already exists", "SLUG_ALREADY_EXISTS", 409)
        
    # Create Tenant
    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        status="trial",
        owner_email=body.owner_email,
        owner_phone=body.owner_phone,
        country=body.country,
        currency=body.currency,
        timezone=body.timezone,
        language=body.language
    )
    db.add(tenant)
    db.flush()
    
    # Create Tenant Profile
    profile = TenantProfile(
        tenant_id=tenant.id,
        logo_url=None,
        primary_color=None,
        secondary_color=None,
        domain=None,
        address=None,
        billing_details={}
    )
    db.add(profile)
    
    # Seed standard tenant permissions in tenant_permissions table
    core_perms = [
        {"code": "tenant.update", "name": "Mettre à jour le tenant", "description": "Permet de modifier les paramètres du tenant"},
        {"code": "users.manage", "name": "Gérer les utilisateurs", "description": "Permet d'ajouter, modifier et suspendre des utilisateurs"},
        {"code": "billing.view", "name": "Voir la facturation", "description": "Permet de voir les factures et l'abonnement"},
        {"code": "billing.manage", "name": "Gérer la facturation", "description": "Permet de modifier l'abonnement et le moyen de paiement"},
        {"code": "roles.manage", "name": "Gérer les rôles", "description": "Permet de configurer les rôles et permissions"},
        {"code": "tenant.settings.view", "name": "Voir les paramètres du tenant", "description": "Permet de lire les paramètres chiffrés du tenant"},
        {"code": "tenant.settings.update", "name": "Modifier les paramètres du tenant", "description": "Permet de modifier les paramètres chiffrés du tenant"},
        {"code": "tenant.api_keys.view", "name": "Voir les clés API", "description": "Permet de lister et voir les métadonnées des clés API"},
        {"code": "tenant.api_keys.create", "name": "Créer des clés API", "description": "Permet de générer de nouvelles clés API"},
        {"code": "tenant.api_keys.revoke", "name": "Révoquer des clés API", "description": "Permet de suspendre, révoquer et supprimer des clés API"},
        {"code": "tenant.api_keys.logs.view", "name": "Voir les logs d'API", "description": "Permet de voir l'historique d'utilisation des clés API"},
        {"code": "tenant.webhooks.view", "name": "Voir les webhooks", "description": "Permet de voir les abonnements webhooks"},
        {"code": "tenant.webhooks.create", "name": "Créer des webhooks", "description": "Permet de créer des abonnements webhooks"},
        {"code": "tenant.webhooks.update", "name": "Modifier les webhooks", "description": "Permet de modifier les abonnements webhooks"},
        {"code": "tenant.webhooks.delete", "name": "Supprimer les webhooks", "description": "Permet de supprimer les abonnements webhooks"},
        {"code": "tenant.webhooks.test", "name": "Tester les webhooks", "description": "Permet de tester un webhook avec un événement ping"},
        {"code": "tenant.webhooks.deliveries.view", "name": "Voir les livraisons webhooks", "description": "Permet de voir l'historique des livraisons de webhooks"},
    ]
    
    db_perms = []
    for p in core_perms:
        perm = db.query(TenantPermission).filter(TenantPermission.code == p["code"]).first()
        if not perm:
            perm = TenantPermission(
                code=p["code"],
                name=p["name"],
                description=p["description"]
            )
            db.add(perm)
            db.flush()
        db_perms.append(perm)
        
    # Seed Tenant Roles
    owner_role = TenantRole(
        tenant_id=tenant.id,
        name="owner",
        description="Propriétaire du compte avec tous les privilèges"
    )
    admin_role = TenantRole(
        tenant_id=tenant.id,
        name="admin",
        description="Administrateur avec privilèges étendus"
    )
    user_role = TenantRole(
        tenant_id=tenant.id,
        name="user",
        description="Utilisateur standard du service"
    )
    
    db.add_all([owner_role, admin_role, user_role])
    db.flush()
    
    # Link all permissions to owner role
    for perm in db_perms:
        owner_role.permissions.append(perm)
        # Link some to admin
        if perm.code in ["users.manage", "billing.view", "tenant.update", "tenant.settings.view", "tenant.settings.update"]:
            admin_role.permissions.append(perm)
            
    # Create the owner user
    owner_user = TenantUser(
        tenant_id=tenant.id,
        email=body.owner_email,
        phone=body.owner_phone,
        first_name="Owner",
        last_name="Account",
        password_hash=hash_password("ChangeMe123!"),
        status="active"
    )
    db.add(owner_user)
    db.flush()
    
    # Assign owner role to owner user
    owner_user.roles.append(owner_role)
    
    # Create status history
    history = TenantStatusHistory(
        tenant_id=tenant.id,
        old_status="none",
        new_status="trial",
        reason="Initial provisioning",
        changed_by_admin_id=admin.id
    )
    db.add(history)
    
    db.commit()
    
    return success_response({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
        "owner_email": tenant.owner_email,
        "created_at": tenant.created_at.isoformat()
    }, message="Tenant successfully created and provisioned")

@router.get("/{tenant_id}")
def get_tenant_detail(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise NotFoundException("Tenant not found", "TENANT_NOT_FOUND")
        
    return success_response({
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
        "created_at": tenant.created_at.isoformat(),
        "updated_at": tenant.updated_at.isoformat()
    })

@router.patch("/{tenant_id}")
def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdateRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin)
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise NotFoundException("Tenant not found", "TENANT_NOT_FOUND")
        
    old_status = tenant.status
    
    # Apply updates
    if body.name is not None:
        tenant.name = body.name
    if body.owner_phone is not None:
        tenant.owner_phone = body.owner_phone
    if body.country is not None:
        tenant.country = body.country
    if body.currency is not None:
        tenant.currency = body.currency
    if body.timezone is not None:
        tenant.timezone = body.timezone
    if body.language is not None:
        tenant.language = body.language
        
    if body.status is not None and body.status != old_status:
        tenant.status = body.status
        
        # Track status history and timestamps
        now = datetime.now(timezone.utc)
        if body.status == "suspended":
            tenant.suspended_at = now
        elif body.status == "cancelled":
            tenant.cancelled_at = now
        elif body.status == "deleted":
            tenant.deleted_at = now
            
        history = TenantStatusHistory(
            tenant_id=tenant.id,
            old_status=old_status,
            new_status=body.status,
            reason="Status updated by platform admin",
            changed_by_admin_id=admin.id
        )
        db.add(history)
        
    db.commit()
    
    # Invalidate cache
    try:
        from dymo_saas_core.core.cache_helpers import invalidate_tenant_cache
        invalidate_tenant_cache(tenant.id, tenant.slug)
    except Exception:
        pass
    
    return success_response({
        "id": str(tenant.id),
        "name": tenant.name,
        "status": tenant.status,
        "updated_at": tenant.updated_at.isoformat()
    }, message="Tenant updated successfully")
