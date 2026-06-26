from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.tenant_app.settings.schemas import TenantSettingCreateOrUpdate
from dymo_saas_core.tenant_app.settings.service import get_settings_for_api, save_tenant_setting

router = APIRouter(tags=["Tenant Settings"])

@router.get("")
def list_settings(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.settings.view"))
):
    settings = get_settings_for_api(db, current_user.tenant_id)
    return success_response(data=settings, message="Settings retrieved successfully")

@router.post("")
def update_setting(
    body: TenantSettingCreateOrUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.settings.update"))
):
    setting = save_tenant_setting(db, current_user.tenant_id, body.key, body.value)
    
    # Return the masked version for consistency
    is_encrypted = setting.is_encrypted
    val = "********" if is_encrypted else setting.value
    
    return success_response(
        data={
            "id": str(setting.id),
            "key": setting.key,
            "value": val,
            "is_encrypted": is_encrypted
        },
        message="Setting updated successfully"
    )
