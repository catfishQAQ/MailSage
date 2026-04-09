from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./omnimail.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)
        # 迁移：为已有 DB 添加 ollama_model 列（新建 DB 时由 create_all 处理，已有 DB 执行此语句）
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN ollama_model VARCHAR"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN sync_interval_hours INTEGER DEFAULT 2"))
        except Exception:
            pass  # 列已存在则忽略
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN analysis_system_prompt TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN reply_system_prompt TEXT"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE user_persona ADD COLUMN language VARCHAR DEFAULT 'en-US'"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE user_persona SET language = 'en-US' "
                "WHERE language IS NULL OR TRIM(language) = ''"
            )
        )
        try:
            await conn.execute(text("ALTER TABLE emails ADD COLUMN message_id VARCHAR"))
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE emails SET message_id = id "
                "WHERE message_id IS NULL OR TRIM(message_id) = ''"
            )
        )


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
