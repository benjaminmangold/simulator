import os
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import requests

MEASUREMENT_ID = os.getenv("MEASUREMENT_ID", "").strip()
API_SECRET = os.getenv("API_SECRET", "").strip()
SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "live").strip().lower()

if not MEASUREMENT_ID or not API_SECRET:
    raise SystemExit("Missing MEASUREMENT_ID or API_SECRET (set them as env vars / GitHub secrets).")

LIVE_ENDPOINT = "https://www.google-analytics.com/mp/collect"
DEBUG_ENDPOINT = "https://www.google-analytics.com/debug/mp/collect"
ENDPOINT = DEBUG_ENDPOINT if SIMULATOR_MODE == "debug" else LIVE_ENDPOINT

# Debug defaults (safe, small volume)
DEFAULT_SESSIONS_PER_RUN = 3 if SIMULATOR_MODE == "debug" else 25
DEFAULT_USER_POOL_SIZE = 50 if SIMULATOR_MODE == "debug" else 400

SESSIONS_PER_RUN = int(os.getenv("SESSIONS_PER_RUN", str(DEFAULT_SESSIONS_PER_RUN)))
USER_POOL_SIZE = int(os.getenv("USER_POOL_SIZE", str(DEFAULT_USER_POOL_SIZE)))

BASE_DOMAIN = os.getenv("BASE_DOMAIN", "https://www.lovesdata-test.com").rstrip("/")

# Desktop share randomized per run between 65% and 85%
DESKTOP_SHARE = random.randint(65, 85) / 100.0

# -----------------------------------------------------------------------------
# Pages + products (keeps your original product set)
# -----------------------------------------------------------------------------
PAGES = [
    "/", "/blog/", "/blog/google-analytics-4-course/", "/blog/ga4-events/",
    "/training/", "/courses/", "/contact/", "/about/"
]

PRODUCTS = [
    {"id": "sku_201", "name": "GA4 Complete Course", "category": "Courses", "price": 225.00},
    {"id": "sku_202", "name": "Google Tag Manager Course", "category": "Courses", "price": 225.00},
    {"id": "sku_203", "name": "Looker Studio Course", "category": "Courses", "price": 125.00},
    {"id": "sku_204", "name": "Google Ads Fundamentals Course", "category": "Courses", "price": 225.00},
]

CURRENCIES = ["AUD", "USD"]
LANGUAGES = ["en-au", "en-us", "en-gb", "de-de", "fr-fr"]

# -----------------------------------------------------------------------------
# Traffic sources (preserves your variety)
# -----------------------------------------------------------------------------
TRAFFIC_SOURCES: List[Dict] = [
    # Organic search
    {"type": "utm", "source": "google", "medium": "organic", "campaign": None, "weight": 25, "referrer": "https://www.google.com/"},
    {"type": "utm", "source": "bing", "medium": "organic", "campaign": None, "weight": 7, "referrer": "https://www.bing.com/"},
    {"type": "utm", "source": "yahoo", "medium": "organic", "campaign": None, "weight": 3, "referrer": "https://search.yahoo.com/"},
    {"type": "utm", "source": "duckduckgo", "medium": "organic", "campaign": None, "weight": 3, "referrer": "https://duckduckgo.com/"},

    # Paid search (cpc)
    {"type": "utm", "source": "google", "medium": "cpc", "campaign": "spring_promotion", "weight": 8, "referrer": None},
    {"type": "utm", "source": "google", "medium": "cpc", "campaign": "performance_max", "weight": 6, "referrer": None},
    {"type": "utm", "source": "google", "medium": "cpc", "campaign": "branded", "weight": 5, "referrer": None},

    # Email
    {"type": "utm", "source": "newsletter", "medium": "email", "campaign": "monthly_update", "weight": 8, "referrer": None},

    # Social / referral / paid social
    {"type": "referral", "source": "facebook.com", "weight": 5, "referrer": "https://facebook.com/"},
    {"type": "referral", "source": "l.instagram.com", "weight": 3, "referrer": "https://l.instagram.com/"},
    {"type": "utm", "source": "facebook.com", "medium": "paid_social", "campaign": "winter_promotion", "weight": 3, "referrer": "https://l.facebook.com/"},
    {"type": "referral", "source": "linkedin.com", "weight": 2, "referrer": "https://www.linkedin.com/"},
    {"type": "utm", "source": "linkedin.com", "medium": "paid_social", "campaign": "summer_promotion", "weight": 2, "referrer": "https://www.linkedin.com/"},

    # Referrals
    {"type": "referral", "source": "benjaminmangold.com", "weight": 1, "referrer": "https://benjaminmangold.com/"},
    {"type": "referral", "source": "youtube.com", "weight": 2, "referrer": "https://www.youtube.com/"},

    # AI / LLM referrals
    {"type": "referral", "source": "chatgpt.com", "weight": 2, "referrer": "https://chatgpt.com/"},
    {"type": "referral", "source": "gemini.google.com", "weight": 1, "referrer": "https://gemini.google.com/"},

    # Direct
    {"type": "direct", "source": "(direct)", "medium": "(none)", "campaign": None, "weight": 12, "referrer": None},

    # Quirky entry (cannot reliably force "(not set)" as a session medium via MP)
    {"type": "unknown", "source": "chatgpt.com", "medium": "(not set)", "campaign": None, "weight": 1, "referrer": None},
]

def weighted_choice(options: List[Dict]) -> Dict:
    total = sum(o.get("weight", 1) for o in options)
    r = random.uniform(0, total)
    upto = 0.0
    for o in options:
        w = o.get("weight", 1)
        if upto + w >= r:
            return o
        upto += w
    return options[-1]

def build_url_with_utms(path: str, src: Dict) -> str:
    base = f"{BASE_DOMAIN}{path}"
    params = [f"utm_source={src['source']}", f"utm_medium={src['medium']}"]
    if src.get("campaign"):
        params.append(f"utm_campaign={src['campaign']}")
    joiner = "&" if "?" in base else "?"
    return base + joiner + "&".join(params)

# -----------------------------------------------------------------------------
# Device profiles (UA + resolution + platform/os hints)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DeviceProfile:
    kind: str  # "desktop" or "mobile"
    user_agent: str
    screen_resolution: str
    platform: str
    os_hint: str

DESKTOP_PROFILES: List[DeviceProfile] = [
    DeviceProfile(
        kind="desktop",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        screen_resolution="2560x1440",
        platform="MacIntel",
        os_hint="macOS"
    ),
    DeviceProfile(
        kind="desktop",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        screen_resolution="1920x1080",
        platform="Win32",
        os_hint="Windows"
    ),
]

MOBILE_PROFILES: List[DeviceProfile] = [
    DeviceProfile(
        kind="mobile",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        screen_resolution="390x844",
        platform="iPhone",
        os_hint="iOS"
    ),
    DeviceProfile(
        kind="mobile",
        user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        screen_resolution="412x915",
        platform="Linux armv8l",
        os_hint="Android"
    ),
]

def pick_device_profile() -> DeviceProfile:
    return random.choice(DESKTOP_PROFILES) if random.random() < DESKTOP_SHARE else random.choice(MOBILE_PROFILES)

# -----------------------------------------------------------------------------
# Client IDs / session numbers
# -----------------------------------------------------------------------------
def make_ga_like_client_id() -> str:
    a = random.randint(100000000, 9999999999)
    b = random.randint(100000000, 9999999999)
    return f"{a}.{b}"

CLIENT_ID_POOL = [make_ga_like_client_id() for _ in range(USER_POOL_SIZE)]
SESSION_NUMBER_BY_CLIENT: Dict[str, int] = {cid: 0 for cid in CLIENT_ID_POOL}

def next_session_number(client_id: str) -> int:
    SESSION_NUMBER_BY_CLIENT[client_id] = SESSION_NUMBER_BY_CLIENT.get(client_id, 0) + 1
    return SESSION_NUMBER_BY_CLIENT[client_id]

# -----------------------------------------------------------------------------
# Networking helpers
# -----------------------------------------------------------------------------
def send_mp(payload: Dict, user_agent: str) -> Tuple[int, Optional[Dict]]:
    params = {"measurement_id": MEASUREMENT_ID, "api_secret": API_SECRET}
    headers = {"User-Agent": user_agent, "Content-Type": "application/json"}
    resp = requests.post(ENDPOINT, params=params, json=payload, headers=headers, timeout=20)
    data = None
    if SIMULATOR_MODE == "debug":
        try:
            data = resp.json()
        except Exception:
            data = None
    return resp.status_code, data

def print_validation(data: Optional[Dict]) -> None:
    if not data:
        return
    msgs = data.get("validationMessages") or []
    if msgs:
        print("Validation messages:")
        for m in msgs:
            desc = m.get("description") or str(m)
            print(f" - {desc}")

def event_payload(client_id: str, event: Dict, timestamp_micros: int, user_properties: Optional[Dict]) -> Dict:
    payload: Dict = {"client_id": client_id, "events": [event], "timestamp_micros": int(timestamp_micros)}
    if user_properties:
        payload["user_properties"] = user_properties
    return payload

def micros_from_ms(ms: int) -> int:
    return ms * 1000

# -----------------------------------------------------------------------------
# Simulation core
# -----------------------------------------------------------------------------
def simulate_one_session(client_id: str) -> None:
    ga_session_id = int(datetime.now(tz=timezone.utc).timestamp())
    ga_session_number = next_session_number(client_id)

    lang = random.choice(LANGUAGES)
    device = pick_device_profile()
    src = weighted_choice(TRAFFIC_SOURCES)

    user_props = {
        "simulator": {"value": "ga4_traffic_sim"},
        "device_kind": {"value": device.kind},
    }

    base_ms = int(time.time() * 1000)

    # Choose pages for this session (ensure at least 2 pageviews for engagement)
    page_count = random.randint(2, 6)
    paths = random.sample(PAGES, k=min(page_count, len(PAGES)))

    first_path = paths[0]
    page_referrer = None

    if src["type"] == "utm":
        first_url = build_url_with_utms(first_path, src)
        page_referrer = src.get("referrer")
    elif src["type"] == "referral":
        first_url = f"{BASE_DOMAIN}{first_path}"
        page_referrer = src.get("referrer") or f"https://{src['source']}/"
    elif src["type"] == "direct":
        first_url = f"{BASE_DOMAIN}{first_path}"
        page_referrer = None
    else:  # "unknown"
        first_url = f"{BASE_DOMAIN}{first_path}"
        page_referrer = None

    # FIRST page_view (t=0) — acquisition happens here (UTMs/referrer)
    pv1_params = {
        "ga_session_id": ga_session_id,
        "ga_session_number": ga_session_number,
        "page_location": first_url,
        "page_title": first_path.strip("/").title() or "Home",
        "language": lang,
        "screen_resolution": device.screen_resolution,
        "platform": device.platform,
        "os_hint": device.os_hint,
        "engagement_time_msec": random.randint(50, 250),
    }
    if page_referrer:
        pv1_params["page_referrer"] = page_referrer

    status, data = send_mp(event_payload(client_id, {"name": "page_view", "params": pv1_params}, micros_from_ms(base_ms), user_props), device.user_agent)
    print_validation(data)
    print(f"[{client_id[:10]}...] Sent: page_view | Status: {status}")

    # Engagement helper event at +12s (75% of sessions)
    if random.random() < 0.75:
        scroll_params = {
            "ga_session_id": ga_session_id,
            "ga_session_number": ga_session_number,
            "language": lang,
            "engagement_time_msec": random.randint(800, 2500),
        }
        status, data = send_mp(event_payload(client_id, {"name": "scroll", "params": scroll_params}, micros_from_ms(base_ms + 12_000), user_props), device.user_agent)
        print_validation(data)
        print(f"[{client_id[:10]}...] Sent: scroll | Status: {status}")

    # Additional page_views
    t_cursor = 15_000
    for path in paths[1:]:
        url = f"{BASE_DOMAIN}{path}"
        params = {
            "ga_session_id": ga_session_id,
            "ga_session_number": ga_session_number,
            "page_location": url,
            "page_title": path.strip("/").title() or "Home",
            "language": lang,
            "engagement_time_msec": random.randint(200, 1200),
        }
        status, data = send_mp(event_payload(client_id, {"name": "page_view", "params": params}, micros_from_ms(base_ms + t_cursor), user_props), device.user_agent)
        print_validation(data)
        print(f"[{client_id[:10]}...] Sent: page_view | Status: {status}")
        t_cursor += random.randint(3_000, 8_000)

    # Ecommerce funnel (25% of sessions)
    if random.random() < 0.25:
        product = random.choice(PRODUCTS)
        currency = random.choice(CURRENCIES)
        price = float(product["price"])

        item = {
            "item_id": product["id"],
            "item_name": product["name"],
            "item_category": product["category"],
            "price": price,
            "quantity": 1,
        }

        def send_ecom(name: str, extra_params: Optional[Dict], offset_ms: int):
            params = {
                "ga_session_id": ga_session_id,
                "ga_session_number": ga_session_number,
                "currency": currency,
                "items": [item],
                "language": lang,
                "engagement_time_msec": random.randint(150, 900),
            }
            if extra_params:
                params.update(extra_params)
            status, data = send_mp(event_payload(client_id, {"name": name, "params": params}, micros_from_ms(base_ms + offset_ms), user_props), device.user_agent)
            print_validation(data)
            print(f"[{client_id[:10]}...] Sent: {name} | Status: {status}")

        send_ecom("view_item", {"value": price}, 4_000)

        if random.random() < 0.60:
            send_ecom("add_to_cart", {"value": price}, 8_000)

            if random.random() < 0.55:
                send_ecom("begin_checkout", {"value": price}, 13_000)

                if random.random() < 0.35:
                    send_ecom(
                        "purchase",
                        {
                            "transaction_id": str(uuid.uuid4()),
                            "value": price,
                            "tax": round(price * 0.1, 2),
                            "shipping": 0.0,
                        },
                        22_000
                    )

def main() -> None:
    mode_label = "DEBUG" if SIMULATOR_MODE == "debug" else "LIVE"
    print(f"{mode_label} traffic simulation. Desktop share this run: {int(DESKTOP_SHARE*100)}%")
    for _ in range(SESSIONS_PER_RUN):
        client_id = random.choice(CLIENT_ID_POOL)
        simulate_one_session(client_id)
        time.sleep(random.uniform(0.2, 0.6))

if __name__ == "__main__":
    main()
