import asyncpg
from contextlib import asynccontextmanager
from app.config import config

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.database_url, min_size=1, max_size=10
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    assert _pool is not None, "DB pool not initialized — call init_pool() first"
    return _pool


@asynccontextmanager
async def acquire(actor_id: int | None = None):
    """Connection helper that sets app.actor_id so audit triggers know WHO acted."""
    async with pool().acquire() as conn:
        if actor_id is not None:
            await conn.execute("SELECT set_config('app.actor_id', $1, true)", str(actor_id))
        yield conn
