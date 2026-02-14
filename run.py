import asyncio
import uvicorn
import database as db


async def start_bot():
    from bot import dp, bot
    await dp.start_polling(bot)


async def start_server():
    from server import app
    from config import HOST, PORT

    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await db.init_db()
    print("✅ Database initialized")
    print("🚀 Starting WatchTogether Bot + Server...")
    await asyncio.gather(start_bot(), start_server())


if __name__ == "__main__":
    asyncio.run(main())