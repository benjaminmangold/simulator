import os
import random
import time
import uuid
import requests
from datetime import datetime, timezone

MEASUREMENT_ID = os.getenv("MEASUREMENT_ID")
API_SECRET = os.getenv("API_SECRET")

if not MEASUREMENT_ID or not API_SECRET:
    raise RuntimeError("Missing MEASUREMENT_ID and/or API_SECRET environment variables.")

# --- Run-level device mix (requested) ---
DESKTOP_SHARE = random.uniform(0.65, 0.85)

# --- Pools / options ---
def generate_client_id() -> str:
    # GA-style client_id looks like two large integers separated by a dot.
    return f"{random.randint(1000000000, 9999999999)}.{random.randint(1000000000, 9999999999)}"

USER_POOL = [generate_client_id() for _ in range(800)]

# Session traffic sources (extend as you like)
TRAFFIC_SOURCES = [
    {"medium": "organic", "source": "google"},
    {"medium": "organic", "source": "bing"},
    {"medium": "organic", "source": "yahoo"},
    {"medium": "organic", "source": "duckduckgo"},
    {"medium": "cpc", "source": "google", "campaign": "spring+promotion"},
    {"medium": "cpc", "source": "google", "campaign": "performance+max"},
    {"medium": "cpc", "source": "google", "campaign": "branded"},
    {"medium": "email", "source": "newsletter", "campaign": "monthly+update"},
    {"medium": "referral", "source": "facebook.com"},
    {"medium": "referral", "source": "l.instagram.com"},
    {"medium": "paid", "source": "facebook.com", "campaign": "winter+promotion"},
    {"medium": "referral", "source": "linkedin.com"},
    {"medium": "paid", "source": "linkedin.com", "campaign": "summer+promotion"},
    {"medium": "referral", "source": "benjaminmangold.com"},
    {"medium": "referral", "source": "youtube.com"},
    {"medium": "(none)", "source": "(direct)"},
    {"medium": "referral", "source": "chatgpt.com"},
    {"medium": "referral", "source": "gemini.google.com"},
    {"medium": "(not set)", "source": "chatgpt.com"},
]

def weighted_random_traffic_source():
    # Bias toward a more realistic mix.
    roll = random.random()
    if roll < 0.45:
        return {"medium": "organic", "source": "google"}
    if roll < 0.60:
        return {"medium": "(none)", "source": "(direct)"}
    if roll < 0.72:
        return {"medium": "cpc", "source": "google", "name": random.choice(["performance+mac", "branded", "spring+promotion"])}
    if roll < 0.84:
        return {"medium": "referral", "source": random.choice(["facebook.com", "l.instagram.com", "youtube.com"])}
    if roll < 0.92:
        return {"medium": "email", "source": "newsletter", "name": random.choice(["welcome+series", "promotion"])}
    return random.choice(TRAFFIC_SOURCES)

# Use standard language tags so GA4 doesn't bucket as "other"
LANGUAGES = [
    ("en-us", 0.70),
    ("en-au", 0.10),
    ("en-gb", 0.07),
    ("de-de", 0.04),
    ("fr-fr", 0.04),
    ("es-es", 0.03),
    ("nl-nl", 0.02),
]

def weighted_choice(weighted_items):
    r = random.random()
    acc = 0.0
    for item, w in weighted_items:
        acc += w
        if r <= acc:
            return item
    return weighted_items[-1][0]

# Device profiles (UA drives GA4 device details; screen/OS/platform are matched)
DESKTOP_PROFILES = [
    {
        "label": "Desktop Chrome (Windows)",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "screen_resolution": "1920x1080",
        "os": "Windows",
        "platform_hint": "desktop",
    },
    {
        "label": "Desktop Chrome (macOS)",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "screen_resolution": "2560x1440",
        "os": "macOS",
        "platform_hint": "desktop",
    },
    {
        "label": "Desktop Safari (macOS)",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "screen_resolution": "1440x900",
        "os": "macOS",
        "platform_hint": "desktop",
    },
]

MOBILE_PROFILES = [
    {
        "label": "iPhone Safari (iOS)",
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "screen_resolution": "390x844",
        "os": "iOS",
        "platform_hint": "mobile",
    },
    {
        "label": "Android Chrome (Pixel)",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "screen_resolution": "412x915",
        "os": "Android",
        "platform_hint": "mobile",
    },
]

# Countries for geo signals (optional; GA4 geo is primarily IP-derived)
COUNTRIES = ["AU", "NZ", "US", "GB", "CA", "DE", "FR", "NL"]

# Ecommerce products
PRODUCTS = [
    {"id": "sku_201", "name": "GA4 Complete Course", "category": "Courses", "price": 225.00},
    {"id": "sku_202", "name": "Google Tag Manager Course", "category": "Courses", "price": 225.00},
    {"id": "sku_203", "name": "Looker Studio Course", "category": "Courses", "price": 125.00},
    {"id": "sku_204", "name": "Google Ads Fundamentals Course", "category": "Courses", "price": 225.00},
]

BASE_URL = os.getenv("BASE_URL", "https://www.lovesdata-test.com")

def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)

def send_event(payload: dict, user_agent: str):
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={MEASUREMENT_ID}&api_secret={API_SECRET}"
    headers = {"User-Agent": user_agent}
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    event_name = payload.get("events", [{}])[0].get("name", "unknown")
    print(f"[{payload['client_id'][:12]}...] Sent: {event_name} | Status: {response.status_code}")

def make_item(product: dict, quantity: int = 1) -> dict:
    return {
        "item_id": product["id"],
        "item_name": product["name"],
        "item_category": product["category"],
        "price": float(product["price"]),
        "quantity": int(quantity),
    }

def choose_device_profile() -> dict:
    if random.random() < DESKTOP_SHARE:
        return random.choice(DESKTOP_PROFILES)
    return random.choice(MOBILE_PROFILES)

def simulate_session(client_id: str, purchase_chance: float = 0.2):
    session_id = random.randint(10_000_000, 99_999_999)
    language = weighted_choice(LANGUAGES)
    device = choose_device_profile()
    country = random.choice(COUNTRIES)
    traffic = weighted_random_traffic_source()

    # Timestamp base for this session (ms)
    t0_ms = _now_ms()

    # Common payload fields shared by all events in this session
    common = {
        "client_id": client_id,
        # Sending traffic_source on session start / first hit makes session acquisition populate.
        "traffic_source": {
            "source": traffic["source"],
            "medium": traffic["medium"],
            **({"name": traffic["name"]} if "name" in traffic else {}),
        },
    }

    # Common event params (kept consistent through the session)
    common_params = {
        "session_id": session_id,
        "language": language,
        "screen_resolution": device["screen_resolution"],
        # These hints won't drive GA4's built-in device dimensions (UA does),
        # but they are useful as custom parameters.
        "device_hint": device["platform_hint"],
        "os_hint": device["os"],
        "country_hint": country,
    }

    def emit(event_name: str, offset_ms: int, params: dict):
        payload = {
            **common,
            "timestamp_micros": int((t0_ms + offset_ms) * 1000),
            "events": [{"name": event_name, "params": params}],
        }
        send_event(payload, user_agent=device["user_agent"])

    # --- Session start ---
    emit(
        "session_start",
        0,
        {
            **common_params,
            # engagement_time_msec is important for realistic engagement metrics when using MP.
            "engagement_time_msec": 1,
        },
    )

    # --- First page view (home) ---
    emit(
        "page_view",
        100,
        {
            **common_params,
            "page_location": f"{BASE_URL}/",
            "page_title": "Home",
            "engagement_time_msec": 100,
        },
    )

    # --- Ensure engagement for most sessions ---
    # 75% of sessions: add a delayed engagement event after 12–25s
    if random.random() < 0.75:
        delay = random.randint(12_000, 25_000)
        emit(
            random.choice(["scroll", "user_engagement"]),
            delay,
            {
                **common_params,
                "engagement_time_msec": delay,
            },
        )

    # 45% of sessions: second page view (helps engaged session definition)
    if random.random() < 0.45:
        pv2_delay = random.randint(4_000, 18_000)
        emit(
            "page_view",
            pv2_delay,
            {
                **common_params,
                "page_location": f"{BASE_URL}/blog/",
                "page_title": "Blog",
                "engagement_time_msec": pv2_delay,
            },
        )

    # --- Ecommerce behavior ---
    # Some sessions are shopping sessions, some just browse.
    is_shopping_session = random.random() < 0.35

    if is_shopping_session:
        product = random.choice(PRODUCTS)
        items = [make_item(product, quantity=1)]

        # view_item
        emit(
            "view_item",
            2_000,
            {
                **common_params,
                "currency": "USD",
                "value": float(product["price"]),
                "items": items,
                "engagement_time_msec": 2_000,
            },
        )

        # add_to_cart (not everyone adds)
        if random.random() < 0.35:
            emit(
                "add_to_cart",
                6_000,
                {
                    **common_params,
                    "currency": "USD",
                    "value": float(product["price"]),
                    "items": items,
                    "engagement_time_msec": 6_000,
                },
            )

        # begin_checkout (subset)
        begin_checkout = random.random() < 0.20
        if begin_checkout:
            emit(
                "begin_checkout",
                11_000,
                {
                    **common_params,
                    "currency": "USD",
                    "value": float(product["price"]),
                    "items": items,
                    "engagement_time_msec": 11_000,
                },
            )

        # purchase (subset; also gated by purchase_chance argument)
        if begin_checkout and (random.random() < purchase_chance):
            transaction_id = str(uuid.uuid4())
            emit(
                "purchase",
                20_000,
                {
                    **common_params,
                    "transaction_id": transaction_id,
                    "currency": "USD",
                    "value": float(product["price"]),
                    "tax": round(float(product["price"]) * 0.1, 2),
                    "shipping": random.choice([0.0, 9.95, 14.95]),
                    "items": items,
                    "engagement_time_msec": 20_000,
                },
            )

def main():
    # Randomize volume by day type (kept similar to your original structure, but higher user pool)
    today = datetime.utcnow().weekday()
    is_weekend = today in (5, 6)

    if is_weekend:
        num_users = random.randint(10, 30)
        session_range = (1, 2)
        purchase_chance = 0.12
        print(f"Weekend traffic simulation. Desktop share this run: {DESKTOP_SHARE:.0%}")
    else:
        num_users = random.randint(40, 120)
        session_range = (1, 3)
        purchase_chance = 0.22
        print(f"Weekday traffic simulation. Desktop share this run: {DESKTOP_SHARE:.0%}")

    sampled_users = random.sample(USER_POOL, num_users)

    # Returning user behavior:
    # - 25% of users get an extra session to create returning sessions.
    returning_boost = set(random.sample(sampled_users, k=max(1, int(len(sampled_users) * 0.25))))

    for client_id in sampled_users:
        sessions = random.randint(*session_range)
        if client_id in returning_boost:
            sessions += 1

        for _ in range(sessions):
            simulate_session(client_id, purchase_chance=purchase_chance)
            # Short delay between sessions to avoid identical ingestion timestamps
            time.sleep(random.uniform(0.2, 1.2))

if __name__ == "__main__":
    main()
