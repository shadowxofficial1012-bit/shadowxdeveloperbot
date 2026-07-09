import asyncio
import json
from urllib.parse import urlencode
from config import OSINT_API_NUMBER_URL, OSINT_API_NUMLEAK_URL, OSINT_API_KEY

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def _fetch_curl(url: str, params: dict) -> dict:
    """Fetch data using curl via async subprocess to bypass TLS fingerprinting."""
    param_str = urlencode(params)
    full_url = f"{url}?{param_str}"
    for attempt in range(MAX_RETRIES):
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", full_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0 and stdout:
                data = json.loads(stdout.decode())
                return {"success": True, "data": data}
            else:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return {"success": False, "error": f"curl failed: {stderr.decode()[:200]}"}
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"success": False, "error": "API request timed out"}
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Max retries exceeded"}


async def lookup_number(number: str) -> dict:
    """Fetch phone number OSINT data from the /api/number endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_curl(OSINT_API_NUMBER_URL, params)


async def lookup_numleak(number: str) -> dict:
    """Fetch phone number leak data from the /api/numleak endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_curl(OSINT_API_NUMLEAK_URL, params)
