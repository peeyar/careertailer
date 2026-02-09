import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
import os
from dotenv import load_dotenv

load_dotenv()

# We need the Async Driver for this script
# Note: Replaces 'postgresql://' with 'postgresql+asyncpg://' for SQLAlchemy Async
DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")

async def init_models():
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        print("⏳ Creating tables...")
        # This deletes tables if they exist (Clean Slate) - REMOVE in Prod!
        await conn.run_sync(Base.metadata.drop_all)
        # This creates the new tables
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables Created: user_skill_bank, resume_cache")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_models())