import asyncio
import asyncpg

async def test():
    try:
        conn = await asyncpg.connect("postgresql://postgres:123123@127.0.0.1:5432/users")
        print("✅ Подключение успешно!")
        await conn.close()
    except Exception as e:
        print("❌ Ошибка:", e)

asyncio.run(test())