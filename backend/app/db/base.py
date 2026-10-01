"""Unit of work over the app engine (tech.md §16.1)."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker


class UnitOfWork:
    """One transaction per `async with uow:`: commit on success, roll back on error.

    Services wrap their writes in it; repositories read `uow.session` inside the block.
    """

    def __init__(self, bind: AsyncEngine | AsyncConnection) -> None:
        # Objects stay readable after commit: async code cannot lazy-load expired attributes.
        # On a connection inside a transaction (contract tests) a commit releases a savepoint.
        self._sessions = async_sessionmaker(
            bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("uow.session exists only inside `async with uow:`")
        return self._session

    async def __aenter__(self) -> AsyncSession:
        if self._session is not None:
            # A nested block would commit and close the outer transaction's session.
            raise RuntimeError("UnitOfWork is already open: nest services, not transactions")
        self._session = self._sessions()
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session, self._session = self.session, None
        try:
            if exc_type is None:
                await session.commit()
        finally:
            await session.close()  # rolls back whatever was not committed
