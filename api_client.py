import logging
import asyncio
from typing import Optional
from config import OSINT_API_NUMBER_URL, OSINT_API_NUMLEAK_URL, OSINT_API_NUMTOUPI_URL, OSINT_API_VEHICLE_URL, OSINT_API_KEY, API_RELAY_URL

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
}

# Flat-format success keys for APIs that don't use nested structures
_FLAT_VEHICLE_KEYS = {"regNo", "owner", "maker", "model", "manufacturer", "registration_number", "vehicle_class"}
_FLAT_UPI_KEYS = {"vpa", "name", "bank", "account_holder", "upi_id"}


def _has_meaningful_data(data: dict) -> bool:
    """Check if the API response contains any meaningful data across all known formats."""
    # Standard nested format keys (use 'in' to handle empty list/empty dict)
    if ("results" in data or data.get("chain") or data.get("calltracer") or 
        data.get("data") or data.get("vehicle") or data.get("owner") or 
        data.get("upi") or data.get("account") or data.get("transaction")):
        return True
    # Flat format success indicators
    if data.get("status") == "success" or data.get("success") is True:
        return True
    # Flat vehicle keys
    if _FLAT_VEHICLE_KEYS & set(data.keys()):
        return True
    # Flat UPI keys
    if _FLAT_UPI_KEYS & set(data.keys()):
        return True
    # Any non-empty response keys means we got data
    if len(data) > 0:
        return True
    return False


def _try_relay(url: str, params: dict, timeout: int) -> Optional[dict]:
    """Try fetching through the relay proxy. Returns None if relay is not configured or fails."""
    if not API_RELAY_URL:
        return None
    try:
        from curl_cffi import requests as cffi_requests
        relay_params = {"url": url, **params}
        resp = cffi_requests.get(
            API_RELAY_URL, params=relay_params, headers=HEADERS,
            impersonate="chrome", timeout=timeout
        )
        if resp.status_code == 200:
            data = resp.json()
            # Check for API-level errors before checking for meaningful data
            if data.get("error") or data.get("success") is False:
                logger.warning(f"Relay: API returned error for {url}: {data.get('error')}")
                return None  # Fallback to direct
            if _has_meaningful_data(data):
                logger.info(f"Relay successful for {url}")
                return {"success": True, "data": data}
            else:
                logger.warning(f"Relay returned empty data for {url}")
                return None  # Try direct
        logger.warning(f"Relay HTTP {resp.status_code} for {url}, trying direct...")
        return None
    except Exception as e:
        logger.warning(f"Relay failed for {url}: {e}, trying direct...")
        return None


def _try_direct(url: str, params: dict, timeout: int) -> dict:
    """Fetch directly from the API endpoint."""
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(
            url, params=params, headers=HEADERS,
            impersonate="chrome", timeout=timeout
        )
        return _process_response(resp)
    except ImportError:
        return _try_direct_requests(url, params, timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _try_direct_requests(url: str, params: dict, timeout: int) -> dict:
    """Direct fetch using requests library."""
    try:
        import requests
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        return _process_response(resp)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _process_response(resp) -> dict:
    """Process HTTP response into standard format."""
    if resp.status_code == 200:
        try:
            data = resp.json()
        except Exception as e:
            return {"success": False, "error": f"Invalid JSON response: {e}"}
        # Check for API-level errors first
        if data.get("success") is False or data.get("error"):
            return {"success": False, "error": data.get("error", "API returned error")}
        if _has_meaningful_data(data):
            return {"success": True, "data": data}
        # Last resort: if the response has any keys, treat it as data
        if isinstance(data, dict) and len(data.keys()) > 0:
            return {"success": True, "data": data}
        return {"success": False, "error": "API returned empty data"}
    elif resp.status_code == 403:
        return {"success": False, "error": "API blocked (403 Forbidden)"}
    else:
        return {"success": False, "error": f"HTTP {resp.status_code}"}


def _fetch_with_fallback(url: str, params: dict, timeout: int = 3) -> dict:
    """Fetch data, trying relay first if configured, then falling back to direct."""
    # Try relay first
    relay_result = _try_relay(url, params, timeout)
    if relay_result is not None:
        return relay_result
    
    # Fall back to direct
    logger.info(f"Fetching directly from {url}")
    return _try_direct(url, params, timeout)


async def _fetch_fast(url: str, params: dict, timeout: int = 3) -> dict:
    """Fetch data with relay-then-direct fallback."""
    return await asyncio.to_thread(_fetch_with_fallback, url, params, timeout=timeout)


async def lookup_number(number: str, timeout: int = 3) -> dict:
    """Fetch phone number details (name, address, SIM etc) from the /api/number endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMBER_URL, params, timeout=timeout)


async def lookup_numleak(number: str, timeout: int = 3) -> dict:
    """Fetch phone number leak data from the /api/numleak endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMLEAK_URL, params, timeout=timeout)


async def lookup_numtoupi(number: str, timeout: int = 3) -> dict:
    """Fetch UPI details linked to a phone number from the /api/numtoupi endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    return await _fetch_fast(OSINT_API_NUMTOUPI_URL, params, timeout=timeout)


async def lookup_vehicle(plate: str, timeout: int = 3) -> dict:
    """Fetch vehicle registration details from the vehicle API endpoint."""
    params = {"vehicle": plate}
    return await _fetch_fast(OSINT_API_VEHICLE_URL, params, timeout=timeout)
