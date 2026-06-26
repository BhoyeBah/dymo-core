"""Application integration for Dymo SaaS Core."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .routers import build_core_router
from dymo_saas_core.core.config import settings
from dymo_saas_core.core.exceptions import register_exception_handlers
from dymo_saas_core.core.module_registry import register_module


def _register_core_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def api_key_logging_middleware(request: Request, call_next):
        response = await call_next(request)
        api_key_id = getattr(request.state, "api_key_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        if api_key_id and tenant_id:
            try:
                from dymo_saas_core.core.database import SessionLocal
                from dymo_saas_core.models.models import TenantApiKeyLog

                db = SessionLocal()
                try:
                    log = TenantApiKeyLog(
                        tenant_id=tenant_id,
                        api_key_id=api_key_id,
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                    )
                    db.add(log)
                    db.commit()
                finally:
                    db.close()
            except Exception:
                pass
        return response

    @app.middleware("http")
    async def idempotency_middleware(request: Request, call_next):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        response = await call_next(request)

        # Do not cache server errors or already-processing conflicts.
        if response.status_code < 500 and response.status_code != 409:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            from fastapi.responses import Response

            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

            try:
                from dymo_saas_core.core.database import SessionLocal
                from dymo_saas_core.core.idempotency import mark_idempotency_completed

                db = SessionLocal()
                try:
                    scope = f"{request.method}:{request.url.path}"
                    body_str = response_body.decode("utf-8", errors="ignore")
                    mark_idempotency_completed(
                        db=db,
                        idempotency_key=idempotency_key,
                        scope=scope,
                        status_code=response.status_code,
                        response_body=body_str,
                    )
                finally:
                    db.close()
            except Exception:
                pass

        return response


def _register_core_routers(app: FastAPI, modules: Optional[Iterable[Any]] = None) -> None:
    from dymo_saas_core.platform.router import platform_router
    from dymo_saas_core.platform.webhooks import router as webhooks_router
    from dymo_saas_core.tenant_app.router import tenant_app_router

    app.include_router(platform_router, prefix="/api/v1/platform")
    app.include_router(webhooks_router, prefix="/api/v1")

    app.include_router(tenant_app_router, prefix="/api/v1/app")
    app.include_router(build_core_router(), prefix="/api")

    if not modules:
        return

    for module in modules:
        if hasattr(module, "manifest"):
            manifest = module.manifest
        elif isinstance(module, dict) and "manifest" in module:
            manifest = module["manifest"]
        else:
            manifest = module

        register_module(manifest)

        if hasattr(module, "router") and module.router:
            prefix = manifest.get("routes_prefix", f"/api/v1/app/{manifest['key']}")
            app.include_router(module.router, prefix=prefix, tags=[manifest.get("name", "Module")])
        elif isinstance(module, dict) and "router" in module and module["router"]:
            prefix = manifest.get("routes_prefix", f"/api/v1/app/{manifest['key']}")
            app.include_router(module["router"], prefix=prefix, tags=[manifest.get("name", "Module")])

    try:
        from dymo_saas_core.core.database import SessionLocal
        from dymo_saas_core.core.module_registry import sync_modules_to_database

        db = SessionLocal()
        try:
            sync_modules_to_database(db)
        finally:
            db.close()
    except Exception:
        # Safe fallback when database migrations are not yet applied.
        pass


def setup_saas_core(app: FastAPI, modules: Optional[Iterable[Any]] = None) -> None:
    """Register the core routes, middlewares and extension modules on a FastAPI app."""

    register_exception_handlers(app)
    _register_core_middlewares(app)
    _register_core_routers(app, modules=modules)
    app.get("/health", tags=["System"])(lambda: {"status": "healthy", "project": app.title})
