from typing import Dict, List, Any, Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.exceptions import ModuleNotEnabledException
from dymo_saas_core.core.database import get_db

# Global in-memory storage of registered modules
REGISTERED_MODULES: Dict[str, Dict[str, Any]] = {}

def register_module(manifest: Dict[str, Any]) -> None:
    key = manifest.get("key")
    if not key:
        raise ValueError("Module manifest must contain a 'key'")
    REGISTERED_MODULES[key] = manifest

def get_registered_modules() -> List[Dict[str, Any]]:
    return list(REGISTERED_MODULES.values())

def get_module_manifest(module_key: str) -> Optional[Dict[str, Any]]:
    return REGISTERED_MODULES.get(module_key)

def sync_modules_to_database(db: Session) -> List[str]:
    from dymo_saas_core.models.models import AvailableModule, TenantPermission, Plan, PlanLimit
    synced_keys = []
    for r in get_registered_modules():
        m = db.query(AvailableModule).filter(AvailableModule.key == r["key"]).first()
        if not m:
            m = AvailableModule(
                key=r["key"],
                name=r["name"],
                description=r.get("description"),
                version=r["version"],
                minimum_core_version=r["minimum_core_version"],
                category=r.get("category"),
                is_core=r.get("is_core", False),
                is_paid_addon=r.get("is_paid_addon", True),
                routes_prefix=r.get("routes_prefix")
            )
            db.add(m)
        else:
            m.name = r["name"]
            m.description = r.get("description")
            m.version = r["version"]
            m.minimum_core_version = r["minimum_core_version"]
            m.category = r.get("category")
            m.is_core = r.get("is_core", False)
            m.is_paid_addon = r.get("is_paid_addon", True)
            m.routes_prefix = r.get("routes_prefix")
        
        # Sync Permissions
        permissions_list = r.get("permissions", [])
        for perm in permissions_list:
            p = db.query(TenantPermission).filter(TenantPermission.code == perm["code"]).first()
            if not p:
                p = TenantPermission(
                    code=perm["code"],
                    name=perm["name"],
                    description=perm.get("description"),
                    module_key=r["key"]
                )
                db.add(p)
            else:
                p.name = perm["name"]
                p.description = perm.get("description")
                p.module_key = r["key"]
        
        # Sync Limits (Optionally add to existing plans if not present)
        limits_list = r.get("limits", [])
        if limits_list:
            plans = db.query(Plan).all()
            for p_obj in plans:
                for lim in limits_list:
                    pl = db.query(PlanLimit).filter(
                        PlanLimit.plan_id == p_obj.id,
                        PlanLimit.metric_key == lim["metric_key"]
                    ).first()
                    if not pl:
                        pl = PlanLimit(
                            plan_id=p_obj.id,
                            metric_key=lim["metric_key"],
                            limit_value=lim["limit_value"],
                            period=lim.get("period", "monthly"),
                            overage_allowed=lim.get("overage_allowed", False),
                            overage_unit_price=0.0
                        )
                        db.add(pl)
                        
        synced_keys.append(r["key"])
    db.commit()
    return synced_keys

def is_module_enabled_for_tenant(db: Session, tenant_id: Any, module_key: str) -> bool:
    from dymo_saas_core.core.cache import cache_service
    from dymo_saas_core.models.models import TenantModule, Subscription, PlanModule, AvailableModule
    
    cache_key = f"dymo:tenant_modules:{tenant_id}"
    cached_modules = None
    try:
        cached_modules = cache_service.get(cache_key)
    except Exception:
        pass

    if cached_modules is not None and isinstance(cached_modules, list):
        return module_key in cached_modules

    # Cache miss: query database to build the set of enabled modules
    # 1. Core modules (always enabled)
    core_modules = db.query(AvailableModule).filter(AvailableModule.is_core == True).all()
    enabled = {m.key for m in core_modules}

    # 2. Fetch overrides
    overrides = db.query(TenantModule).filter(TenantModule.tenant_id == tenant_id).all()
    override_dict = {tm.module_key: tm.is_enabled for tm in overrides}

    # 3. Plan modules
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status.in_(["active", "trialing"])
    ).first()
    if sub:
        plan_modules = db.query(PlanModule).filter(PlanModule.plan_id == sub.plan_id).all()
        for pm in plan_modules:
            if override_dict.get(pm.module_key) is not False:
                enabled.add(pm.module_key)

    # 4. Explicit overrides
    for m_key, is_enabled in override_dict.items():
        if is_enabled:
            enabled.add(m_key)
        else:
            enabled.discard(m_key)

    enabled_list = list(enabled)
    try:
        cache_service.set(cache_key, enabled_list, ttl=300)
    except Exception:
        pass

    return module_key in enabled

def require_module(module_key: str):
    """
    FastAPI dependency to check if a module is enabled for the current tenant.
    """
    from dymo_saas_core.core.tenant_context import require_tenant_user
    
    def dependency(
        db: Session = Depends(get_db),
        tenant_user = Depends(require_tenant_user)
    ):
        if not is_module_enabled_for_tenant(db, tenant_user.tenant_id, module_key):
            raise ModuleNotEnabledException(f"Module '{module_key}' is not enabled for this tenant")
        return tenant_user
    return dependency
