import aiosqlite
import logging
from ..config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.db_path


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                media_type  TEXT NOT NULL,   -- 'movie' | 'series'
                title       TEXT NOT NULL,
                external_id INTEGER,          -- tmdbId or tvdbId
                status      TEXT DEFAULT 'requested',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications_sent (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key   TEXT UNIQUE NOT NULL,  -- dedup key
                sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialised")


async def log_request(user_id: int, media_type: str, title: str, external_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (user_id, media_type, title, external_id) VALUES (?, ?, ?, ?)",
            (user_id, media_type, title, external_id),
        )
        await db.commit()


async def was_notification_sent(event_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM notifications_sent WHERE event_key = ?", (event_key,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def mark_notification_sent(event_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO notifications_sent (event_key) VALUES (?)", (event_key,)
            )
            await db.commit()
        except Exception:
            pass  # Already exists — that's fine
