import logging
import asyncio
import time
from typing import Optional
from config import (
    API_IP_INFO, API_VEHICLE_FULL, API_VEHICLE_MPARIVAHAN,
    API_NAME_INFO, API_HOTX, API_AADHAAR_FAMILY, API_NUMINFO,
    API_RELAY_URL, ADMIN_IDS,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Track relay failures per URL
_relay_fail_cache: dict[str, float] = {}
_RELAY_COOLDOWN = 60


def _has_meaningful_data(data: dict) -> bool:
    if not isinstance(data, dict):
        return bool(data)
    if data.get("success") is False and data.get("error"):
        return False
    if len(data) > 0:
        return True
    return False


def _try_direct(url: str, params: dict, timeout: int) -> dict:
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, params=params, headers=HEADERS, impersonate="chrome", timeout=timeout)
        return _process_response(resp)
    except ImportError:
        return _try_direct_requests(url, params, timeout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _try_direct_requests(url: str, params: dict, timeout: int) -> dict:
    try:
        import requests
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        return _process_response(resp)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _process_response(resp) -> dict:
    if resp.status_code == 200:
        try:
            data = resp.json()
        except Exception as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
        if data.get("success") is False or data.get("error"):
            return {"success": False, "error": data.get("error", "API returned error")}
        if _has_meaningful_data(data):
            return {"success": True, "data": data}
        return {"success": False, "error": "Empty data"}
    elif resp.status_code == 403:
        return {"success": False, "error": "API blocked (403)"}
    else:
        return {"success": False, "error": f"HTTP {resp.status_code}"}


def _sanitize_error(error: str) -> str:
    if not error:
        return "Unknown error"
    e = error.lower()
    if "timed out" in e or "timeout" in e:
        return "Server too slow. Try again."
    if "403" in error or "forbidden" in e:
        return "API blocked. Try later."
    if "connection refused" in e or "connection reset" in e:
        return "Connection refused. Try again."
    if "name resolution" in e or "resolve" in e:
        return "Network error."
    if len(error) > 120:
        return error[:120] + "..."
    return error


def _fetch(url: str, params: dict = None, timeout: int = 15) -> dict:
    result = _try_direct(url, params, timeout)
    if not result.get("success"):
        result["error"] = _sanitize_error(result.get("error", "Unknown"))
    return result


async def _fetch_async(url: str, params: dict = None, timeout: int = 15) -> dict:
    return await asyncio.to_thread(_fetch, url, params, timeout)


# ============================================================
# SERVICE 1: IP INFO
# ============================================================
async def lookup_ip_info(ip: str, timeout: int = 15) -> dict:
    params = {"ip": ip}
    return await _fetch_async(API_IP_INFO, params, timeout)


# ============================================================
# SERVICE 2: FULL VEHICLE INFO
# ============================================================
async def lookup_vehicle_full(plate: str, timeout: int = 20) -> dict:
    params = {"chu": plate}
    return await _fetch_async(API_VEHICLE_FULL, params, timeout)


# ============================================================
# SERVICE 3: M-PARIVAHAN VEHICLE
# ============================================================
async def lookup_vehicle_parivahan(plate: str, timeout: int = 20) -> dict:
    url = f"{API_VEHICLE_MPARIVAHAN}={plate}"
    return await _fetch_async(url, timeout=timeout)


# ============================================================
# SERVICE 4: NAME INFO
# ============================================================
async def lookup_name_info(name: str, timeout: int = 15) -> dict:
    params = {"name": name}
    return await _fetch_async(API_NAME_INFO, params, timeout)


# ============================================================
# SERVICE 5: HOTX (Phone Lookup)
# ============================================================
async def lookup_hotx(number: str, timeout: int = 15) -> dict:
    params = {"number": number}
    return await _fetch_async(API_HOTX, params, timeout)


# ============================================================
# SERVICE 6: AADHAAR FAMILY
# ============================================================
async def lookup_aadhaar_family(aadhaar: str, timeout: int = 15) -> dict:
    params = {"aadhaar": aadhaar}
    return await _fetch_async(API_AADHAAR_FAMILY, params, timeout)


# ============================================================
# SERVICE 7: NUM INFO
# ============================================================
async def lookup_numinfo(number: str, timeout: int = 15) -> dict:
    params = {"number": number}
    return await _fetch_async(API_NUMINFO, params, timeout)


# ============================================================
# HEALTH CHECK
# ============================================================
async def check_api_health() -> list[dict]:
    import time as _time
    endpoints = [
        {"name": "IP Info", "url": API_IP_INFO, "params": {"ip": "8.8.8.8"}, "timeout": 10},
        {"name": "Vehicle Full", "url": API_VEHICLE_FULL, "params": {"chu": "UK06BL1506"}, "timeout": 15},
        {"name": "Vehicle Parivahan", "url": API_VEHICLE_MPARIVAHAN + "=UK06BL1506", "params": None, "timeout": 15},
        {"name": "Name Info", "url": API_NAME_INFO, "params": {"name": "test"}, "timeout": 10},
        {"name": "HotX", "url": API_HOTX, "params": {"number": "9999999999"}, "timeout": 10},
        {"name": "Aadhaar Family", "url": API_AADHAAR_FAMILY, "params": {"aadhaar": "123456789012"}, "timeout": 10},
        {"name": "Num Info", "url": API_NUMINFO, "params": {"number": "9999999999"}, "timeout": 10},
    ]

    def _check_one_sync(ep: dict) -> dict:
        start = _time.time()
        try:
            from curl_cffi import requests as cffi_requests
            kwargs = {"headers": HEADERS, "impersonate": "chrome", "timeout": ep["timeout"]}
            if ep["params"] is not None:
                kwargs["params"] = ep["params"]
            resp = cffi_requests.get(ep["url"], **kwargs)
            elapsed_ms = int((_time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"name": ep["name"], "status": "ok", "ms": elapsed_ms, "detail": "200 OK"}
            elif resp.status_code == 403:
                return {"name": ep["name"], "status": "blocked", "ms": elapsed_ms, "detail": "403"}
            else:
                return {"name": ep["name"], "status": "error", "ms": elapsed_ms, "detail": f"HTTP {resp.status_code}"}
        except Exception as e:
            elapsed_ms = int((_time.time() - start) * 1000)
            err = str(e)
            if "timed out" in err.lower():
                return {"name": ep["name"], "status": "timeout", "ms": elapsed_ms, "detail": "Timeout"}
            return {"name": ep["name"], "status": "error", "ms": elapsed_ms, "detail": err[:60]}

    async def _check_one_async(ep: dict) -> dict:
        return await asyncio.to_thread(_check_one_sync, ep)

    results = await asyncio.gather(*[_check_one_async(ep) for ep in endpoints], return_exceptions=True)
    return [r if isinstance(r, dict) else {"name": "unknown", "status": "error", "ms": 0, "detail": str(r)[:60]} for r in results]


# ============================================================
# HEALTH MONITOR
# ============================================================
_last_health_state: dict[str, str] = {}
_bot_instance = None
HEALTH_CHECK_INTERVAL = 300


async def _notify_admins(message: str) -> None:
    if not _bot_instance:
        return
    for admin_id in ADMIN_IDS:
        try:
            await _bot_instance.send_message(admin_id, message, parse_mode="HTML")
        except Exception:
            pass


async def health_monitor_job(context) -> None:
    global _last_health_state
    results = await check_api_health()
    for r in results:
        name, status, ms, detail = r["name"], r["status"], r["ms"], r["detail"]
        prev = _last_health_state.get(name)
        if prev == "ok" and status != "ok":
            await _notify_admins(f"🚨 <b>API DOWN</b>\n{name}: {status.upper()} ({detail})")
        elif prev is not None and prev != "ok" and status == "ok":
            await _notify_admins(f"✅ <b>API Recovered</b>\n{name}: OK ({ms}ms)")
        _last_health_state[name] = status


def start_health_monitor(job_queue, bot=None) -> None:
    global _bot_instance
    _bot_instance = bot
    job_queue.run_repeating(health_monitor_job, interval=HEALTH_CHECK_INTERVAL, first=30, name="api_health_monitor")
