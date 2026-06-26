"""Core API router registry."""

from __future__ import annotations

from typing import Any, Callable

try:  # pragma: no cover - exercised implicitly when FastAPI is installed
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - keeps the package importable in a bare env
    class APIRouter:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.routes: list[tuple[str, str, Callable[..., Any]]] = []

        def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.routes.append(("GET", path, func))
                return func

            return decorator


def build_core_router() -> APIRouter:
    router = APIRouter(tags=["dymo-core"])

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return router
