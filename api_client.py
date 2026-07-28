import logging
import asyncio
import time
from typing import Optional
from config import OSINT_API_NUMLEAK_URL, OSINT_API_NUMTOUPI_URL, OSINT_API_VEHICLE_URL, OSINT_API_KEY, API_RELAY_URL, ADMIN_IDS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
}

# Track relay failures per URL to skip relay faster on repeated 403s
_relay_fail_cache: dict[str, float] = {}  # url -> last failure timestamp
_RELAY_COOLDOWN = 60  # seconds to skip relay after 403

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
    # Skip relay if it recently returned 403 for this URL
    last_fail = _relay_fail_cache.get(url, 0)
    if time.time() - last_fail < _RELAY_COOLDOWN:
        logger.debug(f"Skipping relay for {url} (cooldown active)")
        return None
    try:
        from curl_cffi import requests as cffi_requests
        relay_params = {"url": url, **params}
        # Use longer timeout for relay (it needs to fetch upstream too)
        relay_timeout = max(timeout, 15)
        resp = cffi_requests.get(
            API_RELAY_URL, params=relay_params, headers=HEADERS,
            impersonate="chrome", timeout=relay_timeout
        )
        if resp.status_code == 200:
            data = resp.json()
            # Check for API-level errors before checking for meaningful data
            if data.get("error") or data.get("success") is False:
                logger.warning(f"Relay: API returned error for {url}: {data.get('error')}")
                _relay_fail_cache[url] = time.time()  # Cache failure
                return None  # Fallback to direct
            if _has_meaningful_data(data):
                logger.info(f"Relay successful for {url}")
                _relay_fail_cache.pop(url, None)  # Clear cache on success
                return {"success": True, "data": data}
            else:
                logger.warning(f"Relay returned empty data for {url}")
                return None  # Try direct
        logger.warning(f"Relay HTTP {resp.status_code} for {url}, trying direct...")
        _relay_fail_cache[url] = time.time()  # Cache failure
        return None
    except Exception as e:
        logger.warning(f"Relay failed for {url}: {e}, trying direct...")
        _relay_fail_cache[url] = time.time()  # Cache failure
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


def _sanitize_error(error: str) -> str:
    """Convert raw curl/HTTP errors into user-friendly messages."""
    if not error:
        return "Unknown error"
    error_lower = error.lower()
    if "timed out" in error_lower or "timeout" in error_lower:
        return "Server is taking too long to respond. Please try again."
    if "403" in error or "forbidden" in error_lower:
        return "API access blocked. Please try again later."
    if "connection refused" in error_lower or "connection reset" in error_lower:
        return "Connection refused by server. Please try again."
    if "name resolution" in error_lower or "resolve" in error_lower:
        return "Network error. Please check your connection."
    if "curl" in error_lower and "failed to perform" in error_lower:
        return "Network request failed. Please try again."
    # Truncate long technical errors
    if len(error) > 120:
        return error[:120] + "..."
    return error


def _try_direct_with_headers(url: str, params: dict, timeout: int) -> dict:
    """Direct fetch with alternative headers to bypass 403 blocks."""
    try:
        from curl_cffi import requests as cffi_requests
        # Try with different headers to bypass IP-based blocking
        alt_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/search?q=osint+api",
            "Origin": "https://www.google.com",
        }
        # Try different impersonation values supported by curl_cffi
        # NOTE: "android" is NOT supported on all curl_cffi versions!
        for imp in ["chrome110", "chrome124", "chrome"]:
            try:
                logger.debug(f"Trying alt headers (impersonate={imp}) for {url}")
                resp = cffi_requests.get(
                    url, params=params, headers=alt_headers,
                    impersonate=imp, timeout=timeout
                )
                if resp.status_code == 403:
                    logger.warning(f"Alt headers (impersonate={imp}) also got 403 for {url}")
                    continue
                elif resp.status_code == 200:
                    logger.info(f"Alt headers (impersonate={imp}) returned 200 for {url}")
                    return _process_response(resp)
                else:
                    logger.debug(f"Alt headers (impersonate={imp}) returned {resp.status_code} for {url}")
                    return _process_response(resp)
            except Exception as e:
                err_msg = str(e)
                # Skip unsupported impersonation values silently
                if "not supported" in err_msg.lower():
                    logger.debug(f"Impersonation '{imp}' not supported, trying next...")
                    continue
                logger.debug(f"Alt headers (impersonate={imp}) failed for {url}: {e}")
                continue
        # All impersonation attempts failed
        logger.warning(f"All alt header attempts failed for {url}")
        return {"success": False, "error": "All alternative header attempts failed"}
    except ImportError:
        # curl_cffi not available, fall back to requests library
        try:
            import requests
            alt_headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/search?q=osint+api",
            }
            resp = requests.get(url, params=params, headers=alt_headers, timeout=timeout)
            return _process_response(resp)
        except Exception as e:
            logger.warning(f"Alt headers request failed for {url}: {e}")
            return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning(f"Alt headers request failed for {url}: {e}")
        return {"success": False, "error": str(e)}


def _fetch_with_fallback(url: str, params: dict, timeout: int = 15, max_retries: int = 2) -> dict:
    """Fetch data, trying relay first if configured, then falling back to direct with retries."""
    # Try relay first
    relay_result = _try_relay(url, params, timeout)
    if relay_result is not None:
        return relay_result
    
    # Fall back to direct with retries
    logger.info(f"Fetching directly from {url}")
    last_error = None
    last_raw_error = None
    for attempt in range(max_retries):
        result = _try_direct(url, params, timeout)
        if result.get("success"):
            return result
        last_error = result.get("error", "Unknown error")
        last_raw_error = last_error
        # Don't retry on 403 (API blocked) - try alternative headers instead
        if "403" in str(last_error) or "blocked" in str(last_error).lower():
            logger.warning(f"Got 403 from direct request, trying alternative headers for {url}")
            alt_result = _try_direct_with_headers(url, params, timeout)
            if alt_result.get("success"):
                logger.info(f"403 bypass SUCCEEDED for {url} with alternative headers")
                return alt_result
            else:
                alt_raw = alt_result.get("error", last_raw_error)
                logger.warning(f"403 bypass FAILED for {url}: {alt_raw}")
                alt_result["raw_error"] = alt_raw
                alt_result["error"] = _sanitize_error(alt_raw)
                return alt_result
        if attempt < max_retries - 1:
            logger.info(f"Retry {attempt + 1}/{max_retries} for {url}")
            time.sleep(1)  # 1s delay between retries
    # Store raw error for logging, sanitize for user display
    return {"success": False, "error": _sanitize_error(last_error or "All retries failed"), "raw_error": last_raw_error}


async def _fetch_fast(url: str, params: dict, timeout: int = 15) -> dict:
    """Fetch data with relay-then-direct fallback."""
    return await asyncio.to_thread(_fetch_with_fallback, url, params, timeout=timeout)


async def lookup_numleak(number: str, timeout: int = 15) -> dict:
    """Fetch phone number leak data from the /api/numleak endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    result = await _fetch_fast(OSINT_API_NUMLEAK_URL, params, timeout=timeout)
    if not result.get("success") and result.get("error") and not result.get("raw_error"):
        result["raw_error"] = result["error"]
        result["error"] = _sanitize_error(result["error"])
    return result


async def lookup_numtoupi(number: str, timeout: int = 15) -> dict:
    """Fetch UPI details linked to a phone number from the /api/numtoupi endpoint."""
    params = {"key": OSINT_API_KEY, "num": number}
    result = await _fetch_fast(OSINT_API_NUMTOUPI_URL, params, timeout=timeout)
    if not result.get("success") and result.get("error") and not result.get("raw_error"):
        result["raw_error"] = result["error"]
        result["error"] = _sanitize_error(result["error"])
    return result


async def lookup_vehicle(plate: str, timeout: int = 25) -> dict:
    """Fetch vehicle registration details from the vehicle API endpoint."""
    params = {"vehicle": plate, "key": OSINT_API_KEY}
    result = await _fetch_fast(OSINT_API_VEHICLE_URL, params, timeout=timeout)
    if not result.get("success") and result.get("error") and not result.get("raw_error"):
        result["raw_error"] = result["error"]
        result["error"] = _sanitize_error(result["error"])
    return result


# --- Health Check ---
async def check_api_health() -> list[dict]:
    """Check health of all API endpoints. Returns a list of status dicts."""
    import time as _time

    endpoints = [
        {"name": "Numleak (Phone Lookup)", "url": OSINT_API_NUMLEAK_URL, "params": {"key": OSINT_API_KEY, "num": "9999999999"}, "timeout": 10},
        {"name": "UPI Lookup", "url": OSINT_API_NUMTOUPI_URL, "params": {"key": OSINT_API_KEY, "num": "9999999999"}, "timeout": 10},
        {"name": "Vehicle", "url": OSINT_API_VEHICLE_URL, "params": {"vehicle": "MH00AA0000", "key": OSINT_API_KEY}, "timeout": 15},
    ]

    if API_RELAY_URL:
        endpoints.append({"name": "Relay Proxy", "url": API_RELAY_URL + "/health", "params": {}, "timeout": 10})

    def _check_one_sync(ep: dict) -> dict:
        """Synchronous health check for a single endpoint."""
        start = _time.time()
        try:
            from curl_cffi import requests as cffi_requests
            resp = cffi_requests.get(
                ep["url"], params=ep["params"], headers=HEADERS,
                impersonate="chrome", timeout=ep["timeout"]
            )
            elapsed_ms = int((_time.time() - start) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                # Even 200 can have API-level errors
                if data.get("success") is False and data.get("error"):
                    return {"name": ep["name"], "status": "error", "ms": elapsed_ms, "detail": data["error"][:60]}
                return {"name": ep["name"], "status": "ok", "ms": elapsed_ms, "detail": "200 OK"}
            elif resp.status_code == 403:
                return {"name": ep["name"], "status": "blocked", "ms": elapsed_ms, "detail": "403 Forbidden"}
            else:
                return {"name": ep["name"], "status": "error", "ms": elapsed_ms, "detail": f"HTTP {resp.status_code}"}
        except Exception as e:
            elapsed_ms = int((_time.time() - start) * 1000)
            err = str(e)
            if "timed out" in err.lower() or "timeout" in err.lower():
                return {"name": ep["name"], "status": "timeout", "ms": elapsed_ms, "detail": "Timed out"}
            return {"name": ep["name"], "status": "error", "ms": elapsed_ms, "detail": err[:60]}

    # Run all checks in parallel using to_thread to avoid blocking event loop
    async def _check_one_async(ep: dict) -> dict:
        return await asyncio.to_thread(_check_one_sync, ep)

    results = await asyncio.gather(*[_check_one_async(ep) for ep in endpoints], return_exceptions=True)
    final = []
    for r in results:
        if isinstance(r, Exception):
            final.append({"name": "unknown", "status": "error", "ms": 0, "detail": str(r)[:60]})
        else:
            final.append(r)
    return final


# --- Background Health Monitor ---
# Tracks previous state to detect transitions (ok -> down, down -> ok)
_last_health_state: dict[str, str] = {}  # endpoint_name -> last status
_bot_instance = None  # Telegram bot instance for sending admin notifications

HEALTH_CHECK_INTERVAL = 300  # 5 minutes


async def _notify_admins(message: str) -> None:
    """Send a notification message to all admin users."""
    if not _bot_instance:
        return
    for admin_id in ADMIN_IDS:
        try:
            await _bot_instance.send_message(admin_id, message, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"[Health] Could not notify admin {admin_id}: {e}")


async def health_monitor_job(context) -> None:
    """Background job: check API health, log warnings, and notify admins on state changes."""
    global _last_health_state
    results = await check_api_health()

    for r in results:
        name = r["name"]
        status = r["status"]
        ms = r["ms"]
        detail = r["detail"]
        prev = _last_health_state.get(name)

        # State transition: went DOWN
        if prev == "ok" and status != "ok":
            logger.warning(f"[Health] {name}: DOWN ⚠️ - was OK, now {status.upper()} ({detail}, {ms}ms)")
            await _notify_admins(
                f"🚨 <b>API Endpoint DOWN</b>\n\n"
                f"<b>Endpoint:</b> {name}\n"
                f"<b>Status:</b> {status.upper()}\n"
                f"<b>Detail:</b> {detail}\n"
                f"<b>Response:</b> {ms}ms\n\n"
                f"Running auto-retry with alternative headers."
            )

        # State transition: RECOVERED
        elif prev is not None and prev != "ok" and status == "ok":
            logger.info(f"[Health] {name}: RECOVERED ✅ - was {prev.upper()}, now OK ({ms}ms)")
            await _notify_admins(
                f"✅ <b>API Endpoint Recovered</b>\n\n"
                f"<b>Endpoint:</b> {name}\n"
                f"<b>Previous:</b> {prev.upper()}\n"
                f"<b>Status:</b> OK ({ms}ms)"
            )

        # First run with issues
        elif prev is None and status != "ok":
            logger.warning(f"[Health] {name}: {status.upper()} - {detail} ({ms}ms)")
            await _notify_admins(
                f"⚠️ <b>API Endpoint Issue on Startup</b>\n\n"
                f"<b>Endpoint:</b> {name}\n"
                f"<b>Status:</b> {status.upper()}\n"
                f"<b>Detail:</b> {detail}"
            )

        # First run OK (just log, no notification)
        elif prev is None and status == "ok":
            logger.info(f"[Health] {name}: OK ({ms}ms)")

        # Still down (log but don't spam notifications)
        elif status != "ok" and ms > 5000:
            logger.warning(f"[Health] {name}: STILL DOWN - {status.upper()} ({detail}, {ms}ms)")

        _last_health_state[name] = status

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "ok")
    total = len(results)
    if ok_count < total:
        logger.warning(f"[Health] {ok_count}/{total} endpoints healthy")
    else:
        logger.info(f"[Health] All {total} endpoints healthy")


def start_health_monitor(job_queue, bot=None) -> None:
    """Start the background health monitor job."""
    global _bot_instance
    _bot_instance = bot
    job_queue.run_repeating(
        health_monitor_job,
        interval=HEALTH_CHECK_INTERVAL,
        first=30,  # First check after 30 seconds of bot startup
        name="api_health_monitor",
    )
    logger.info(f"[Health] Background monitor started (interval: {HEALTH_CHECK_INTERVAL}s)")
    if bot:
        logger.info(f"[Health] Admin notifications enabled for {len(ADMIN_IDS)} admin(s)")
