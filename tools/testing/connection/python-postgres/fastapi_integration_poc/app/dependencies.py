from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields an async database session.
    Ensures connection is closed after request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # You can add automated commit here if desired:
            # await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Type alias for easier injection in routes
SessionDep = Annotated[AsyncSession, Depends(get_db)]
