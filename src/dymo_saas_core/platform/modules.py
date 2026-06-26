from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.module_registry import get_registered_modules
from dymo_saas_core.models.models import AvailableModule

router = APIRouter(tags=["Platform Modules"])

@router.get("")
def list_modules(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    modules = db.query(AvailableModule).all()
    return success_response([
        {
            "key": m.key,
            "name": m.name,
            "description": m.description,
            "version": m.version,
            "minimum_core_version": m.minimum_core_version,
            "category": m.category,
            "is_core": m.is_core,
            "is_paid_addon": m.is_paid_addon,
            "routes_prefix": m.routes_prefix
        }
        for m in modules
    ])

@router.post("/sync")
def sync_modules(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    registered = get_registered_modules()
    synced_keys = []
    
    for r in registered:
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
            # Update attributes
            m.name = r["name"]
            m.description = r.get("description")
            m.version = r["version"]
            m.minimum_core_version = r["minimum_core_version"]
            m.category = r.get("category")
            m.is_core = r.get("is_core", False)
            m.is_paid_addon = r.get("is_paid_addon", True)
            m.routes_prefix = r.get("routes_prefix")
        synced_keys.append(r["key"])
        
    db.commit()
    return success_response({"synced_keys": synced_keys}, message="Modules synchronized successfully")
