"""Queries of the user settings (tech.md §5.1)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.users import UserSettings


async def get(session: AsyncSession, user_id: UUID) -> UserSettings | None:
    return await session.get(UserSettings, user_id)
