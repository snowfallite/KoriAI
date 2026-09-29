"""Caches and service tables (tech.md §5.6)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.schema.base import Base, Json, Now


class WebCache(Base):
    __tablename__ = "web_cache"
    __table_args__ = (CheckConstraint("kind in ('search','extract','crawl','map')", name="kind"),)

    key_hash: Mapped[bytes] = mapped_column(primary_key=True)  # sha256(kind + query)
    kind: Mapped[str]
    request: Mapped[Json]
    response: Mapped[Json]
    credits: Mapped[int]
    created_at: Mapped[Now]
    expires_at: Mapped[datetime]


Index("web_cache_expires_idx", WebCache.expires_at)


class JobMarker(Base):
    """Effect of demo.echo and the idempotency harness."""

    __tablename__ = "job_markers"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    created_at: Mapped[Now]
