import logging
import json
import asyncio
from urllib.parse import urlencode
from config import OSINT_API_NUMBER_URL, OSINT_API_NUMLEAK_URL, OSINT_API_KEY

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_requests(url: str, params: dict) -> dict:
    """Fetch data using requests library (synchronous fallback)."""
    try:
        import requests
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _fetch_httpx_sync(url: str, params: dict) -> dict:
    """Fetch data using httpx library (synchronous fallback)."""
    try:
        import httpx
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, params=params, headers=HEADERS)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _fetch_curl(url: str, params: dict) -> dict:
    """Fetch data using curl via async subprocess."""
    param_str = urlencode(params)
    full_url = f"{url}?{param_str}"
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "--max-time", "30", full_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=35)
        if proc.returncode == 0 and stdout:
            data = json.loads(stdout.decode())
            return {"success": True, "data": data}
        else:
            return {"success": False, "error": f"curl failed: {stderr.decode()[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _fetch_with_fallback(url: str, params: dict) -> dict:
    """Try multiple methods to fetch data, starting with the most reliable."""
    # Method 1: Try requests (most reliable on Windows/Docker)
    result = await asyncio.to_thread(_fetch_requests, url, params)
    if result["success"]:
        logger.info("API call succeeded via requests")
        return result
    logger.warning(f"requests failed: {result.get('error')}")

    # Method 2: Try httpx
    result = await asyncio.to_thread(_fetch_httpx_sync, url, params)
    if result["success"]:
        logger.info("API call succeeded via httpx")
        return result
    logger.warning(f"httpx failed: {result.get('error')}")

    # Method 3: Try curl
    result = await _fetch_curl(url, params)
    if result["success"]:
        logger.info("API call succeeded via curl")
        return result
    logger.warning(f"curl failed: {result.get('error')}")

    return {"success": False, "error": "All API methods failed"}


async def lookup_number(number: str) -> dict:
    """Fetch phone number OSINT data from the /api/number endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    for attempt in range(MAX_RETRIES):
        result = await _fetch_with_fallback(OSINT_API_NUMBER_URL, params)
        if result["success"]:
            return result
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    return result


async def lookup_numleak(number: str) -> dict:
    """Fetch phone number leak data from the /api/numleak endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    for attempt in range(MAX_RETRIES):
        result = await _fetch_with_fallback(OSINT_API_NUMLEAK_URL, params)
        if result["success"]:
            return result
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    return result
