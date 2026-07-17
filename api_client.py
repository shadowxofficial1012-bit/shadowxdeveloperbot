import logging
import asyncio
from config import OSINT_API_NUMBER_URL, OSINT_API_NUMLEAK_URL, OSINT_API_NUMTOUPI_URL, OSINT_API_VEHICLE_URL, OSINT_API_KEY, API_RELAY_URL

logger = logging.getLogger(__name__)

MAX_RETRIES = 1
RETRY_DELAY = 0  # seconds - no delay for speed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
}


def _fetch_cffi(url: str, params: dict, timeout: int = 8) -> dict:
    """Fetch data using curl_cffi (bypasses TLS fingerprinting). Supports relay proxy."""
    try:
        from curl_cffi import requests as cffi_requests
        # If relay URL is set, proxy the request through it
        if API_RELAY_URL:
            resp = cffi_requests.get(
                API_RELAY_URL, params={"url": url, **params}, headers=HEADERS,
                impersonate="chrome", timeout=timeout
            )
        else:
            resp = cffi_requests.get(
                url, params=params, headers=HEADERS, impersonate="chrome", timeout=timeout
            )
        if resp.status_code == 200:
            data = resp.json()
            # Check for various success indicators across different API types
            if (data.get("results") or data.get("chain") or data.get("calltracer") or 
                data.get("status") == "success" or data.get("success") == True or
                data.get("data") or data.get("vehicle") or data.get("owner") or 
                data.get("upi") or data.get("account") or data.get("transaction")):
                return {"success": True, "data": data}
            elif data.get("success") is False or data.get("error"):
                return {"success": False, "error": data.get("error", "API returned error")}
            else:
                return {"success": False, "error": "API returned empty data"}
        elif resp.status_code == 403:
            return {"success": False, "error": "API blocked (403 Forbidden)"}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except ImportError:
        # curl_cffi not available, fall back to requests
        return _fetch_requests(url, params, timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _fetch_requests(url: str, params: dict, timeout: int = 30) -> dict:
    """Fetch data using requests library. Supports relay proxy."""
    try:
        import requests
        # If relay URL is set, proxy the request through it
        if API_RELAY_URL:
            resp = requests.get(
                API_RELAY_URL, params={"url": url, **params}, headers=HEADERS, timeout=timeout
            )
        else:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            # Check for various success indicators across different API types
            if (data.get("results") or data.get("chain") or data.get("calltracer") or 
                data.get("status") == "success" or data.get("success") == True or
                data.get("data") or data.get("vehicle") or data.get("owner") or 
                data.get("upi") or data.get("account") or data.get("transaction")):
                return {"success": True, "data": data}
            elif data.get("success") is False or data.get("error"):
                return {"success": False, "error": data.get("error", "API returned error")}
            else:
                return {"success": False, "error": "API returned empty data"}
        elif resp.status_code == 403:
            return {"success": False, "error": "API blocked (403 Forbidden)"}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _fetch_fast(url: str, params: dict, timeout: int = 8) -> dict:
    """Fetch data using curl_cffi (fastest method, bypasses TLS fingerprinting)."""
    return await asyncio.to_thread(_fetch_cffi, url, params, timeout=timeout)


async def lookup_number(number: str, timeout: int = 8) -> dict:
    """Fetch phone number details (name, address, SIM etc) from the /api/number endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMBER_URL, params, timeout=timeout)


async def lookup_numleak(number: str, timeout: int = 8) -> dict:
    """Fetch phone number leak data from the /api/numleak endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMLEAK_URL, params, timeout=timeout)


async def lookup_numtoupi(number: str, timeout: int = 8) -> dict:
    """Fetch UPI details linked to a phone number from the /api/numtoupi endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMTOUPI_URL, params, timeout=timeout)


async def lookup_vehicle(plate: str, timeout: int = 8) -> dict:
    """Fetch vehicle registration details from the vehicle API endpoint."""
    params = {"vehicle": plate}
    return await _fetch_fast(OSINT_API_VEHICLE_URL, params, timeout=timeout)
