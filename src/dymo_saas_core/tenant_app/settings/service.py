import uuid
from typing import List, Optional
from sqlalchemy.orm import Session

from dymo_saas_core.models.models import TenantSetting
from dymo_saas_core.core.encryption import encrypt_secret, decrypt_secret

def is_key_sensitive(key: str) -> bool:
    key_lower = key.lower()
    for pattern in ["password", "key", "secret", "token", "credential", "auth", "pass"]:
        if pattern in key_lower:
            return True
    return False

def get_settings_for_api(db: Session, tenant_id: uuid.UUID) -> List[dict]:
    settings = db.query(TenantSetting).filter(TenantSetting.tenant_id == tenant_id).all()
    results = []
    for s in settings:
        val = s.value
        if s.is_encrypted or is_key_sensitive(s.key):
            val = "********"
        results.append({
            "id": s.id,
            "key": s.key,
            "value": val,
            "is_encrypted": s.is_encrypted
        })
    return results

def get_decrypted_setting(db: Session, tenant_id: uuid.UUID, key: str) -> Optional[str]:
    setting = db.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant_id,
        TenantSetting.key == key
    ).first()
    if not setting:
        return None
    if setting.is_encrypted:
        return decrypt_secret(setting.value)
    return setting.value

def save_tenant_setting(db: Session, tenant_id: uuid.UUID, key: str, value: str) -> TenantSetting:
    existing = db.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant_id,
        TenantSetting.key == key
    ).first()

    sensitive = is_key_sensitive(key)

    if existing:
        if sensitive:
            if value == "********":
                # User did not modify the secret field (sent masked placeholder)
                return existing
            existing.value = encrypt_secret(value)
            existing.is_encrypted = True
        else:
            existing.value = value
            existing.is_encrypted = False
        db.commit()
        db.refresh(existing)
        return existing
    else:
        if sensitive:
            val = encrypt_secret(value) if value != "********" else ""
            setting = TenantSetting(
                tenant_id=tenant_id,
                key=key,
                value=val,
                is_encrypted=True
            )
        else:
            setting = TenantSetting(
                tenant_id=tenant_id,
                key=key,
                value=value,
                is_encrypted=False
            )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting
