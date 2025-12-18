import os
import random
import time
import uuid
from datetime import datetime, timezone

import requests

# ----------------------------
# Configuration (via GitHub Secrets / Env Vars)
# ----------------------------
MEASUREMENT_ID = os.getenv("MEASUREMENT_ID")
API_SECRET = os.getenv("API_SECRET")

# Mode switch:
#   SIMULATOR_MODE=live  -> sends to /mp/collect (default)
#   SIMULATOR_MODE=debug -> sends to /mp/debug/collect and prints validationMessages
# Backward-compatible: DEBUG=1 also enables debug mode.
SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "live").strip().lower()
DEBUG_FLAG = os.getenv("DEBUG", "").strip().lower() in ("1", "true", "yes", "y")
DEBUG_MODE = (SIMULATOR_MODE == "debug") or DEBUG_FLAG


if not MEASUREMENT_ID or not API_SECRET:
    raise RuntimeError("Missing MEASUREMENT_ID or API_SECRET environment variables.")

MP_COLLECT = "https://www.google-analytics.com/mp/collect"
MP_DEBUG_COLLECT = "https://www.google-analytics.com/mp/debug/collect"

# ----------------------------
# Debug presets
# When DEBUG_MODE is enabled, we default to smaller volumes unless you explicitly set env vars.
# ----------------------------
def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default

DEFAULT_USER_POOL_SIZE = 50 if DEBUG_MODE else 400
DEFAULT_SESSIONS_PER_RUN = 3 if DEBUG_MODE else 20


# ----------------------------
# Realistic device profiles (UA + matching hints)
# NOTE: UA is sent as an HTTP header (GA4 derives device/OS/browser from it)
# ----------------------------
DESKTOP_PROFILES = [
    {
        "device_category": "desktop",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "screen_resolution": "1440x900",
        "platform": "web",
        "os": "macOS",
    },
    {
        "device_category": "desktop",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "screen_resolution": "1920x1080",
        "platform": "web",
        "os": "Windows",
    },
    {
        "device_category": "desktop",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "screen_resolution": "1920x1080",
        "platform": "web",
        "os": "Linux",
    },
]

MOBILE_PROFILES = [
    {
        "device_category": "mobile",
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "screen_resolution": "390x844",
        "platform": "web",
        "os": "iOS",
    },
    {
        "device_category": "mobile",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "screen_resolution": "412x915",
        "platform": "web",
        "os": "Android",
    },
    {
        "device_category": "mobile",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "screen_resolution": "360x800",
        "platform": "web",
        "os": "Android",
    },
]

# ----------------------------
# Language / geo (language must be an event param to populate Language; GA4 will bucket unknowns as "Other")
# ----------------------------
LANGUAGES = [
    ("en-au", 0.72),
    ("en-us", 0.10),
    ("en-gb", 0.08),
    ("de-de", 0.03),
    ("fr-fr", 0.03),
    ("es-es", 0.02),
    ("nl-nl", 0.02),
]

COUNTRIES = [
    ("Australia", 0.70),
    ("United States", 0.10),
    ("United Kingdom", 0.08),
    ("Canada", 0.05),
    ("New Zealand", 0.04),
    ("Germany", 0.02),
    ("France", 0.01),
]

# ----------------------------
# Traffic sources (session-level). This will populate Session source/medium when sent at session start.
# ----------------------------
TRAFFIC_SOURCES = [
    ({"source": "google", "medium": "organic"}, 0.35),
    ({"source": "bing", "medium": "organic"}, 0.06),
    ({"source": "direct", "medium": "(none)"}, 0.20),
    ({"source": "newsletter", "medium": "email", "campaign": "monthly_update"}, 0.10),
    ({"source": "facebook.com", "medium": "paid", "campaign": "winter_promo"}, 0.07),
    ({"source": "instagram.com", "medium": "paid", "campaign": "reels_promo"}, 0.05),
    ({"source": "linkedin.com", "medium": "referral"}, 0.05),
    ({"source": "google", "medium": "cpc", "campaign": "spring_promotion"}, 0.12),
]

# ----------------------------
# Site + ecommerce
# ----------------------------
HOST = "https://demo.lovesdata-test.com"

PAGES = [
    "/",
    "/blog/",
    "/blog/google-analytics-4/",
    "/blog/google-tag-manager/",
    "/courses/",
    "/ga4-complete-course/",
    "/gtm-course/",
    "/contact/",
]

PRODUCTS = [
    {"item_id": "sku_ga4_course", "item_name": "GA4 Complete Course", "item_category": "Courses", "price": 199.0},
    {"item_id": "sku_gtm_course", "item_name": "Google Tag Manager Course", "item_category": "Courses", "price": 149.0},
    {"item_id": "sku_looker_course", "item_name": "Looker Studio Course", "item_category": "Courses", "price": 129.0},
]

CURRENCY = "AUD"

# ----------------------------
# Helpers
# ----------------------------
def weighted_choice(weighted):
    r = random.random()
    cumulative = 0.0
    for item, w in weighted:
        cumulative += w
        if r <= cumulative:
            return item
    return weighted[-1][0]

def make_client_id():
    # GA-style client_id tends to look like "1234567890.1234567890"
    return f"{random.randint(1000000000, 9999999999)}.{random.randint(1000000000, 9999999999)}"

def now_micros():
    return int(time.time() * 1_000_000)

def send_mp(payload, user_agent):
    endpoint = MP_DEBUG_COLLECT if DEBUG_MODE else MP_COLLECT
    url = f"{endpoint}?measurement_id={MEASUREMENT_ID}&api_secret={API_SECRET}"

    headers = {
        "User-Agent": user_agent,
        "Content-Type": "application/json",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=20)

    if DEBUG_MODE:
        try:
            data = resp.json()
            msgs = data.get("validationMessages", [])
            if msgs:
                print("Validation messages:")
                for m in msgs[:10]:
                    print(f" - {m.get('description')}")
        except Exception:
            pass

    return resp.status_code

# ----------------------------
# Simulator core
# ----------------------------
def build_device_profile(desktop_share):
    if random.random() < desktop_share:
        return random.choice(DESKTOP_PROFILES)
    return random.choice(MOBILE_PROFILES)

def simulate_session(client_id, session_number, desktop_share, purchase_session_chance=0.25):
    # GA4 sessions are stitched using ga_session_id + ga_session_number
    ga_session_id = random.randint(1_000_000_000, 2_000_000_000)

    device = build_device_profile(desktop_share)
    lang = weighted_choice(LANGUAGES)
    country = weighted_choice(COUNTRIES)
    traffic = weighted_choice(TRAFFIC_SOURCES)

    # Base time for this session
    base_ts = now_micros()

    # Common event params (use GA reserved session params)
    common_params = {
        "ga_session_id": ga_session_id,
        "ga_session_number": session_number,
        "language": lang,
        "screen_resolution": device["screen_resolution"],
    }

    # Session-level traffic source
    traffic_source = {
        "source": traffic["source"],
        "medium": traffic["medium"],
    }
    if "campaign" in traffic:
        traffic_source["name"] = traffic["campaign"]

    # 1) session_start (t=0)
    payload = {
        "client_id": client_id,
        "timestamp_micros": base_ts,
        "traffic_source": traffic_source,
        "events": [{
            "name": "session_start",
            "params": {
                **common_params,
                "engagement_time_msec": 1
            }
        }]
    }
    print(f"[{client_id[:12]}...] Sent: session_start | Status: {send_mp(payload, device['user_agent'])}")

    # 2) first page_view (t=+150ms) — include traffic_source again for safety
    first_path = random.choice(PAGES)
    payload = {
        "client_id": client_id,
        "timestamp_micros": base_ts + 150_000,
        "traffic_source": traffic_source,
        "events": [{
            "name": "page_view",
            "params": {
                **common_params,
                "page_location": f"{HOST}{first_path}",
                "page_title": first_path.strip("/").title() or "Home",
                "engagement_time_msec": random.randint(10, 200)
            }
        }]
    }
    print(f"[{client_id[:12]}...] Sent: page_view | Status: {send_mp(payload, device['user_agent'])}")

    # 3) engagement event after 10–18s for a portion of sessions (drives engaged sessions)
    # We also include a second page_view for most sessions (another engaged criterion)
    engaged_delay_ms = random.randint(10_500, 18_000)
    if random.random() < 0.75:
        payload = {
            "client_id": client_id,
            "timestamp_micros": base_ts + engaged_delay_ms * 1000,
            "events": [{
                "name": "scroll",
                "params": {
                    **common_params,
                    "engagement_time_msec": random.randint(800, 2500)
                }
            }]
        }
        print(f"[{client_id[:12]}...] Sent: scroll | Status: {send_mp(payload, device['user_agent'])}")

    # 4) additional page views (t=+12–40s spread)
    pageviews = random.sample(PAGES, random.randint(1, 3))
    t_ms = random.randint(12_000, 16_000)
    for path in pageviews:
        t_ms += random.randint(4_000, 12_000)
        payload = {
            "client_id": client_id,
            "timestamp_micros": base_ts + t_ms * 1000,
            "events": [{
                "name": "page_view",
                "params": {
                    **common_params,
                    "page_location": f"{HOST}{path}",
                    "page_title": path.strip("/").title() or "Home",
                    "engagement_time_msec": random.randint(300, 1800)
                }
            }]
        }
        print(f"[{client_id[:12]}...] Sent: page_view | Status: {send_mp(payload, device['user_agent'])}")

    # 5) Ecommerce funnel for some sessions
    if random.random() < purchase_session_chance:
        product = random.choice(PRODUCTS)
        items = [{
            "item_id": product["item_id"],
            "item_name": product["item_name"],
            "item_category": product["item_category"],
            "price": product["price"],
            "quantity": 1
        }]

        # view_item (t=+2–6s)
        t_ms = random.randint(2_000, 6_000)
        payload = {
            "client_id": client_id,
            "timestamp_micros": base_ts + t_ms * 1000,
            "events": [{
                "name": "view_item",
                "params": {
                    **common_params,
                    "currency": CURRENCY,
                    "value": product["price"],
                    "items": items,
                    "engagement_time_msec": random.randint(200, 800)
                }
            }]
        }
        print(f"[{client_id[:12]}...] Sent: view_item | Status: {send_mp(payload, device['user_agent'])}")

        # add_to_cart (25–55% of shopping sessions)
        if random.random() < 0.45:
            t_ms += random.randint(2_000, 7_000)
            payload = {
                "client_id": client_id,
                "timestamp_micros": base_ts + t_ms * 1000,
                "events": [{
                    "name": "add_to_cart",
                    "params": {
                        **common_params,
                        "currency": CURRENCY,
                        "value": product["price"],
                        "items": items,
                        "engagement_time_msec": random.randint(200, 900)
                    }
                }]
            }
            print(f"[{client_id[:12]}...] Sent: add_to_cart | Status: {send_mp(payload, device['user_agent'])}")

            # begin_checkout (40–70% of add_to_cart)
            if random.random() < 0.55:
                t_ms += random.randint(2_000, 7_000)
                payload = {
                    "client_id": client_id,
                    "timestamp_micros": base_ts + t_ms * 1000,
                    "events": [{
                        "name": "begin_checkout",
                        "params": {
                            **common_params,
                            "currency": CURRENCY,
                            "value": product["price"],
                            "items": items,
                            "engagement_time_msec": random.randint(400, 1400)
                        }
                    }]
                }
                print(f"[{client_id[:12]}...] Sent: begin_checkout | Status: {send_mp(payload, device['user_agent'])}")

                # purchase (25–55% of begin_checkout)
                if random.random() < 0.40:
                    t_ms += random.randint(4_000, 12_000)
                    payload = {
                        "client_id": client_id,
                        "timestamp_micros": base_ts + t_ms * 1000,
                        "events": [{
                            "name": "purchase",
                            "params": {
                                **common_params,
                                "transaction_id": str(uuid.uuid4()),
                                "currency": CURRENCY,
                                "value": product["price"],
                                "items": items,
                                "engagement_time_msec": random.randint(800, 2500)
                            }
                        }]
                    }
                    print(f"[{client_id[:12]}...] Sent: purchase | Status: {send_mp(payload, device['user_agent'])}")

def main():
    # Random split each run: 65%–85% desktop
    desktop_share = random.uniform(0.65, 0.85)
    mode_label = "DEBUG" if DEBUG_MODE else "LIVE"
    print(f"{mode_label} traffic simulation. Desktop share this run: {round(desktop_share*100)}%")

    # Bigger user pool to avoid "hundreds of sessions, <10 users"
    user_pool_size = _env_int("USER_POOL_SIZE", DEFAULT_USER_POOL_SIZE)
    sessions_per_run = _env_int("SESSIONS_PER_RUN", DEFAULT_SESSIONS_PER_RUN)

    # Keep a stable pool for this run
    users = [make_client_id() for _ in range(user_pool_size)]
    session_numbers = {cid: 0 for cid in users}

    for _ in range(sessions_per_run):
        cid = random.choice(users)
        session_numbers[cid] += 1
        simulate_session(cid, session_numbers[cid], desktop_share)
        # Small pacing gap so we don't burst too aggressively
        time.sleep(random.uniform(0.2, 0.7))

if __name__ == "__main__":
    main()
