from datetime import datetime
from ipaddress import ip_address
from zoneinfo import ZoneInfo


REGION_MATCH_BONUS = 0.08
TIME_SLOT_MATCH_BONUS = 0.05
REGION_TIME_COMBO_BONUS = 0.03
CONTEXT_BONUS_CAP = 0.12

TIME_SLOT_WINDOWS = (
    ("night", 0, 6),
    ("morning", 6, 10),
    ("noon", 10, 14),
    ("afternoon", 14, 18),
    ("evening", 18, 24),
)

REGION_HEADER_CANDIDATES = (
    "CF-IPCountry",
    "X-Vercel-IP-Country",
    "X-Appengine-Country",
    "X-Country-Code",
    "X-Geo-Country",
)

INVALID_REGION_CODES = {"XX", "T1", "ZZ", "UNKNOWN"}


def normalize_region_code(value):
    if not value:
        return None
    normalized = str(value).strip().upper().replace("_", "-")
    if not normalized or normalized in INVALID_REGION_CODES:
        return None
    return normalized[:32] or None


def normalize_time_slot(value):
    if not value:
        return None
    normalized = str(value).strip().lower()
    valid_slots = {name for name, _, _ in TIME_SLOT_WINDOWS}
    return normalized if normalized in valid_slots else None


def derive_time_slot(dt):
    if not dt:
        return None
    hour = dt.hour
    for name, start, end in TIME_SLOT_WINDOWS:
        if start <= hour < end:
            return name
    return "night"


def derive_time_slot_by_timezone(timezone_name):
    if not timezone_name:
        return derive_time_slot(datetime.now())

    try:
        current_dt = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        current_dt = datetime.now()
    return derive_time_slot(current_dt)


def normalize_context_targets(values, normalizer):
    if not values:
        return []
    normalized = []
    for value in values:
        item = normalizer(value)
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def extract_client_ip(req):
    forwarded_for = req.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        for candidate in forwarded_for.split(","):
            ip_value = candidate.strip()
            if ip_value:
                return ip_value
    return (
        req.headers.get("X-Real-IP")
        or req.headers.get("CF-Connecting-IP")
        or req.remote_addr
        or ""
    ).strip()


def is_public_ip(ip_value):
    if not ip_value:
        return False
    try:
        parsed_ip = ip_address(ip_value)
    except ValueError:
        return False
    return not (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_reserved
        or parsed_ip.is_multicast
        or parsed_ip.is_unspecified
    )


def extract_region_from_headers(req):
    for header_name in REGION_HEADER_CANDIDATES:
        region_code = normalize_region_code(req.headers.get(header_name))
        if region_code:
            return region_code
    return None


def build_request_context(req, payload=None):
    payload = payload or {}
    region = (
        extract_region_from_headers(req)
        or normalize_region_code(payload.get("login_region_code"))
        or normalize_region_code(req.args.get("login_region_code"))
    )
    timezone_name = (
        req.headers.get("X-Client-Timezone")
        or payload.get("login_timezone")
        or req.args.get("login_timezone")
    )
    time_slot = normalize_time_slot(
        req.headers.get("X-Client-Time-Slot")
        or payload.get("login_time_slot")
        or req.args.get("login_time_slot")
    )
    if not time_slot:
        time_slot = derive_time_slot_by_timezone(timezone_name)

    client_ip = extract_client_ip(req)

    return {
        "region_code": region,
        "timezone": (timezone_name or "").strip()[:64] or None,
        "time_slot": time_slot,
        "client_ip": client_ip if is_public_ip(client_ip) else None,
    }


def context_from_user(user):
    if not user:
        return {"region_code": None, "timezone": None, "time_slot": None, "client_ip": None}
    return {
        "region_code": normalize_region_code(getattr(user, "last_login_region", None)),
        "timezone": getattr(user, "last_login_timezone", None),
        "time_slot": normalize_time_slot(getattr(user, "last_login_time_slot", None)),
        "client_ip": None,
    }


def resolve_effective_context(user=None, request_context=None):
    request_context = request_context or {}
    user_context = context_from_user(user)
    return {
        "region_code": request_context.get("region_code") or user_context.get("region_code"),
        "timezone": request_context.get("timezone") or user_context.get("timezone"),
        "time_slot": request_context.get("time_slot") or user_context.get("time_slot"),
        "client_ip": request_context.get("client_ip") or user_context.get("client_ip"),
    }


def sync_user_login_context(user, context):
    if not user:
        return
    user.last_login_region = context.get("region_code")
    user.last_login_timezone = context.get("timezone")
    user.last_login_time_slot = context.get("time_slot")
    user.last_active_at = datetime.now()


def effective_post_regions(post):
    explicit_regions = normalize_context_targets(getattr(post, "target_regions", None), normalize_region_code)
    if explicit_regions:
        return explicit_regions

    author = getattr(post, "author", None)
    author_region = normalize_region_code(getattr(author, "last_login_region", None))
    return [author_region] if author_region else []


def effective_post_time_slots(post):
    explicit_slots = normalize_context_targets(getattr(post, "target_time_slots", None), normalize_time_slot)
    if explicit_slots:
        return explicit_slots

    inferred_slot = derive_time_slot(getattr(post, "created_at", None))
    return [inferred_slot] if inferred_slot else []


def compute_post_context_bonus(post, context):
    if not post or not context:
        return 0.0, {"region_match": False, "time_slot_match": False}

    region_code = normalize_region_code(context.get("region_code"))
    time_slot = normalize_time_slot(context.get("time_slot"))

    region_match = bool(region_code and region_code in effective_post_regions(post))
    time_slot_match = bool(time_slot and time_slot in effective_post_time_slots(post))

    bonus = 0.0
    if region_match:
        bonus += REGION_MATCH_BONUS
    if time_slot_match:
        bonus += TIME_SLOT_MATCH_BONUS
    if region_match and time_slot_match:
        bonus += REGION_TIME_COMBO_BONUS

    return min(bonus, CONTEXT_BONUS_CAP), {
        "region_match": region_match,
        "time_slot_match": time_slot_match,
    }
