import asyncio
import sys
import traceback

sys.path.insert(0, ".")

from app.database import AsyncSessionLocal, init_db
from app.services.parse_service import ParseService


async def test():
    await init_db()
    svc = ParseService()
    for mid in [5, 6, 7]:
        print(f"=== Testing material_id={mid} ===")
        async with AsyncSessionLocal() as session:
            try:
                m = await svc.parse_material(mid, session)
                print(f"OK: parser_type={m.parser_type}, status={m.parse_status}")
                await session.commit()
            except Exception as e:
                print(f"FAIL: {e}")
                traceback.print_exc()
                await session.rollback()


asyncio.run(test())
