from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from llmx_advocate.store.db import get_session_factory


async def db_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
