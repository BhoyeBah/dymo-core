from typing import List, Optional, Any
from fastapi import FastAPI

from dymo_saas_core.app import setup_saas_core

def create_app(project_name: str = "dymo-saas-core", modules: Optional[List[Any]] = None) -> FastAPI:
    app = FastAPI(
        title=project_name,
        description="Core B2B Multi-Tenant SaaS platform by Dymotechnologie",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    setup_saas_core(app, modules=modules)

    return app

# Default core application for direct uvicorn execution
app = create_app()
