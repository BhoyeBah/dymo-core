import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import Request, Header, Depends
from sqlalchemy.orm import Session
from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.exceptions import IdempotencyException
from dymo_saas_core.models.models import IdempotencyKey

async def require_idempotency(
    request: Request,
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """
    FastAPI dependency to enforce request idempotency.
    If the idempotency key is already processing, raises a conflict.
    If it is completed, returns the cached response if payload matches, or raises conflict if payload differs.
    Otherwise, marks it as processing.
    """
    if not idempotency_key:
        return None

    # Read and restore request body to allow hashing
    body_bytes = await request.body()
    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}
    request._receive = receive

    scope = f"{request.method}:{request.url.path}"
    request_hash = hashlib.sha256(body_bytes).hexdigest()

    existing = db.query(IdempotencyKey).filter(
        IdempotencyKey.scope == scope,
        IdempotencyKey.key == idempotency_key
    ).first()

    if existing:
        if existing.status == "processing":
            raise IdempotencyException(
                "A request with this idempotency key is already being processed",
                "IDEMPOTENCY_PROCESSING"
            )
        elif existing.status == "completed":
            if existing.request_hash == request_hash:
                from dymo_saas_core.core.exceptions import IdempotencyReturnResponseException
                raise IdempotencyReturnResponseException(
                    status_code=existing.status_code or 200,
                    response_body=existing.response_body or ""
                )
            else:
                raise IdempotencyException(
                    "This idempotency key has already been used with a different request payload",
                    "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
                )

    # Record the key as processing
    try:
        if existing:
            existing.status = "processing"
            existing.request_hash = request_hash
            existing.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            db.commit()
        else:
            record = IdempotencyKey(
                scope=scope,
                key=idempotency_key,
                request_hash=request_hash,
                status="processing",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            db.add(record)
            db.commit()
    except Exception:
        db.rollback()
        raise IdempotencyException(
            "A request with this idempotency key is already being processed",
            "IDEMPOTENCY_PROCESSING"
        )
    return idempotency_key

def mark_idempotency_completed(db: Session, idempotency_key: str, scope: str, status_code: int = 200, response_body: str = ""):
    """Mark an idempotency key process as completed."""
    if not idempotency_key:
        return
    record = db.query(IdempotencyKey).filter(
        IdempotencyKey.scope == scope,
        IdempotencyKey.key == idempotency_key
    ).first()
    if record:
        record.status = "completed"
        record.status_code = status_code
        record.response_body = response_body
        db.commit()
