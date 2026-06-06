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
    """Connection helper that sets app.actor_id so audit triggers know WHO acted.

    Eslatma: asyncpg autocommit rejimida ishlaydi — har bir `execute` alohida
    tranzaksiya. Shuning uchun `app.actor_id` ni SESSIYA darajasida (is_local=false)
    o'rnatamiz; aks holda keyingi (ko'p oyoqli) INSERT'lar uchun actor yo'qoladi.
    Yozuvsiz (actor_id=None) ulanishlarda eski qiymat qolib ketmasligi uchun tozalaymiz.
    """
    async with pool().acquire() as conn:
        await conn.execute(
            "SELECT set_config('app.actor_id', $1, false)",
            str(actor_id) if actor_id is not None else "",
        )
        yield conn
