import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class TimestampMixin:
    pass  # We include base timestamps directly in BaseModel for cleaner inheritance

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        default=None
    )

    def soft_delete(self, user_id: uuid.UUID | None = None) -> None:
        self.deleted_at = datetime.utcnow()
        if user_id:
            self.deleted_by = user_id

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None

class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
