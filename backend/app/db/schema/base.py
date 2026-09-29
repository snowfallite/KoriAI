"""Declarative base for the §5 tables (tech.md §5)."""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

Json = dict[str, object]

UuidPk = Annotated[uuid.UUID, mapped_column(primary_key=True, server_default=text("uuidv7()"))]
IdentityPk = Annotated[int, mapped_column(BigInteger, Identity(always=True), primary_key=True)]
Now = Annotated[datetime, mapped_column(server_default=func.now())]
# tech.md §5: the application sets updated_at, there are no triggers.
UpdatedAt = Annotated[datetime, mapped_column(server_default=func.now(), onupdate=func.now())]


class Base(DeclarativeBase):
    # The §5 DDL leaves constraints unnamed; these templates give PostgreSQL's default names.
    # A CHECK takes its column as the name: CheckConstraint("role in (...)", name="role").
    metadata = MetaData(
        naming_convention={
            "pk": "%(table_name)s_pkey",
            "fk": "%(table_name)s_%(column_0_name)s_fkey",
            "uq": "%(table_name)s_%(column_0_N_name)s_key",
            "ck": "%(table_name)s_%(constraint_name)s_check",
        }
    )
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy reads it as a class-level mapping
        str: Text(),
        datetime: DateTime(timezone=True),
        Json: JSONB(),
        list[Json]: JSONB(),
    }
    # Async sessions cannot lazy-load server-generated values after a flush.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
