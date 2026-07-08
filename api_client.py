import aiohttp
import asyncio
from config import OSINT_API_URL, OSINT_API_KEY


async def lookup_instagram(username: str) -> dict:
    """Fetch Instagram OSINT data for a given username."""
    params = {"key": OSINT_API_KEY, "username": username}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(OSINT_API_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, "data": data}
                else:
                    return {"success": False, "error": f"API returned status {resp.status}"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "API request timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}
