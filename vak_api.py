# vak_api.py
# API layer for smscenter.pro
# - getNumber/getStatus/setStatus: TEXT responses
# - getPrices: JSON response (countries -> services -> {count,cost})

import json
import requests


BASE_URL = "https://smscenter.pro"
HANDLER = "/handler_api.php"
STUBS_HANDLER = "/stubs/handler_api.php"


class SmsCenterError(Exception):
    pass


_TEXT_ERRORS = {
    "BAD_KEY": "BAD_KEY",
    "BAD_SERVICE": "BAD_SERVICE",
    "NO_BALANCE": "NO_BALANCE",
    "NO_NUMBERS": "NO_NUMBERS",
    "NO_ACTIVATION": "NO_ACTIVATION",
}


def _looks_like_html(text: str) -> bool:
    t = (text or "").lstrip().lower()
    return t.startswith("<!doctype") or t.startswith("<html") or "<div id=\"root\"" in t


def _get_text(path: str, params: dict, timeout: int = 20) -> str:
    try:
        r = requests.get(BASE_URL + path, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise SmsCenterError(f"Network error: {e}")

    text = (r.text or "").strip()
    if not text:
        raise SmsCenterError("Empty response from provider")

    # If provider returned website HTML, this means we hit the wrong endpoint or got redirected.
    if _looks_like_html(text):
        raise SmsCenterError("API endpoint returned HTML (wrong path or redirect). Check using /stubs/handler_api.php")

    return text


def _get_text_stubs_first(params: dict, timeout: int = 20) -> str:
    """
    Use STUBS endpoint as primary, fallback to HANDLER.
    """
    try:
        return _get_text(STUBS_HANDLER, params, timeout=timeout)
    except SmsCenterError:
        return _get_text(HANDLER, params, timeout=timeout)


def _get_json(path: str, params: dict, timeout: int = 25):
    """
    Try JSON parse, but provider might return text errors (BAD_KEY, etc.).
    """
    text = _get_text(path, params, timeout=timeout)

    # Known text errors
    if text in _TEXT_ERRORS:
        raise SmsCenterError(text)

    try:
        return json.loads(text)
    except Exception:
        raise SmsCenterError(f"Invalid JSON response (preview): {text[:200]}")


# =========================
# Get Number (TEXT)
# =========================
def get_number(api_key: str, service: str, country: str, operator: str = "any", ref: str = "") -> dict:
    """
    Expected success:
      ACCESS_NUMBER:ID:NUMBER
    Expected errors (examples):
      NO_BALANCE
      NO_NUMBERS
      BAD_KEY
      BAD_SERVICE
    """
    params = {
        "action": "getNumber",
        "api_key": api_key,
        "service": service,
        "country": country,
    }
    if operator:
        params["operator"] = operator
    if ref:
        params["ref"] = ref

    resp = _get_text_stubs_first(params)

    if resp.startswith("ACCESS_NUMBER"):
        parts = resp.split(":")
        if len(parts) >= 3:
            return {"id": parts[1], "number": parts[2]}
        raise SmsCenterError(f"Malformed ACCESS_NUMBER response: {resp}")

    if resp in _TEXT_ERRORS:
        raise SmsCenterError(resp)

    raise SmsCenterError(f"Unknown getNumber response: {resp}")


# =========================
# Get Status (TEXT)
# =========================
def get_status(api_key: str, activation_id: str) -> dict:
    """
    WAIT:
      STATUS_WAIT_CODE
    OK:
      STATUS_OK:12345
    Other possible statuses can appear depending on provider.
    """
    params = {"action": "getStatus", "api_key": api_key, "id": activation_id}
    resp = _get_text_stubs_first(params)

    if resp == "STATUS_WAIT_CODE":
        return {"status": "WAIT"}

    if resp.startswith("STATUS_OK"):
        parts = resp.split(":")
        if len(parts) >= 2:
            return {"status": "OK", "code": parts[1]}
        raise SmsCenterError(f"Malformed STATUS_OK response: {resp}")

    if resp in _TEXT_ERRORS:
        raise SmsCenterError(resp)

    return {"status": "UNKNOWN", "raw": resp}


# =========================
# Set Status (TEXT)
# =========================
def set_status(api_key: str, activation_id: str, status: int) -> bool:
    """
    status:
      8 = cancel
      6 = finish
    """
    params = {"action": "setStatus", "api_key": api_key, "id": activation_id, "status": str(status)}
    resp = _get_text_stubs_first(params)

    if resp in _TEXT_ERRORS:
        raise SmsCenterError(resp)

    # Provider responses vary; treat any non-error as success
    return True


# =========================
# Get Prices (JSON)
# =========================
def get_prices(api_key: str, service: str = "", country: str = "") -> dict:
    """
    /stubs/handler_api.php?action=getPrices&api_key=...&service=...&country=...
    """
    params = {"action": "getPrices", "api_key": api_key}
    if service:
        params["service"] = service
    if country:
        params["country"] = country

    # Primary: stubs endpoint
    try:
        return _get_json(STUBS_HANDLER, params)
    except SmsCenterError:
        # Fallback: main handler
        return _get_json(HANDLER, params)


def normalize_prices(prices_json: dict) -> list:
    """
    Convert nested JSON into a flat list:
      [{"country":"16","service":"wa","count":100,"cost":2.0}, ...]
    """
    out = []
    if not isinstance(prices_json, dict):
        return out

    for c_code, services in prices_json.items():
        if not isinstance(services, dict):
            continue
        for s_code, meta in services.items():
            if not isinstance(meta, dict):
                continue
            try:
                count = int(meta.get("count", 0))
            except Exception:
                count = 0
            try:
                cost = float(meta.get("cost", 0))
            except Exception:
                cost = 0.0

            out.append(
                {
                    "country": str(c_code),
                    "service": str(s_code),
                    "count": count,
                    "cost": cost,
                }
            )
    return out