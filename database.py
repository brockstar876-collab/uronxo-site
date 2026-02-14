import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                total_watch_time INTEGER DEFAULT 0,
                movies_watched INTEGER DEFAULT 0,
                series_watched INTEGER DEFAULT 0,
                rooms_created INTEGER DEFAULT 0,
                messages_sent INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                creator_id INTEGER,
                video_url TEXT DEFAULT '',
                video_title TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT NOT NULL,
                user_id INTEGER,
                username TEXT DEFAULT '',
                text TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );
        """)
        # Defaults
        defaults = {
            "sub_media_type": "none",
            "sub_media_file_id": "",
            "sub_text": "📢 Для доступа подпишитесь на наш канал!",
            "welcome_media_type": "none",
            "welcome_media_file_id": "",
            "welcome_text": "🎬 Добро пожаловать! Откройте мини-приложение для совместного просмотра!",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )
        await db.commit()


async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else ""


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()


async def upsert_user(telegram_id: int, username: str = "", first_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username, first_name)
               VALUES (?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name""",
            (telegram_id, username, first_name),
        )
        await db.commit()


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return await cur.fetchone()


async def update_user_stat(telegram_id: int, field: str, increment: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {field} = {field} + ? WHERE telegram_id=?",
            (increment, telegram_id),
        )
        await db.commit()


async def create_room(code: str, name: str, creator_id: int, video_url: str, video_title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO rooms (code, name, creator_id, video_url, video_title) VALUES (?,?,?,?,?)",
            (code, name, creator_id, video_url, video_title),
        )
        await db.commit()
        await db.execute(
            "UPDATE users SET rooms_created = rooms_created + 1 WHERE telegram_id=?",
            (creator_id,),
        )
        await db.commit()


async def get_room(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM rooms WHERE code=? AND is_active=1", (code,))
        return await cur.fetchone()


async def get_active_rooms():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM rooms WHERE is_active=1 ORDER BY created_at DESC LIMIT 20"
        )
        return await cur.fetchall()


async def close_room(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE rooms SET is_active=0 WHERE code=?", (code,))
        await db.commit()


async def save_message(room_code: str, user_id: int, username: str, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_messages (room_code, user_id, username, text) VALUES (?,?,?,?)",
            (room_code, user_id, username, text),
        )
        await db.commit()


async def get_messages(room_code: str, limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM chat_messages WHERE room_code=? ORDER BY id DESC LIMIT ?",
            (room_code, limit),
        )
        rows = await cur.fetchall()
        return list(reversed(rows))


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM rooms")
        rooms = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM rooms WHERE is_active=1")
        active = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM chat_messages")
        msgs = (await cur.fetchone())[0]
        return {"users": users, "rooms_total": rooms, "rooms_active": active, "messages": msgs}