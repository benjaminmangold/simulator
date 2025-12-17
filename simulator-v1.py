import os
import uuid
import random
import requests
import time
from datetime import datetime

MEASUREMENT_ID = os.getenv("MEASUREMENT_ID")
API_SECRET = os.getenv("API_SECRET")

USER_POOL = [str(uuid.uuid4()) for _ in range(50)]

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
    {"medium": "(not set)", "source": "chatgpt.com"}
]

PAGES = [
    '/home', '/products', '/products/item1', '/cart',
    '/checkout', '/thank-you', '/about', '/blog', '/contact'
]

LANGUAGES = ['en', 'en-US', 'en-GB', 'fr', 'de', 'es']
DEVICES = ['mobile', 'tablet', 'desktop']
COUNTRIES = ['AU', 'US', 'GB', 'DE', 'IN', 'CA']

PRODUCTS = [
    {"id": "sku_101", "name": "Wireless Mouse", "price": 29.99},
    {"id": "sku_102", "name": "Mechanical Keyboard", "price": 89.99},
    {"id": "sku_103", "name": "USB-C Hub", "price": 49.95},
    {"id": "sku_104", "name": "Laptop Stand", "price": 39.50},
    {"id": "sku_105", "name": "Noise Cancelling Headphones", "price": 129.99},
    {"id": "sku_106", "name": "Portable SSD 1TB", "price": 109.99},
    {"id": "sku_107", "name": "Webcam 1080p", "price": 59.00},
    {"id": "sku_108", "name": "Bluetooth Speaker", "price": 79.95},
    {"id": "sku_109", "name": "Smartphone Tripod", "price": 24.00},
    {"id": "sku_110", "name": "Desk Lamp", "price": 45.00}
]

def weighted_random_traffic_source():
    roll = random.random()
    if roll < 0.4:
        return {"medium": "organic", "source": "google"}
    elif roll < 0.6:
        return {"medium": "(none)", "source": "(direct)"}
    else:
        return random.choice([
            ts for ts in TRAFFIC_SOURCES
            if not (ts["medium"] == "organic" and ts["source"] == "google")
            and not (ts["medium"] == "(none)" and ts["source"] == "(direct)")
        ])

def send_event(payload):
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={MEASUREMENT_ID}&api_secret={API_SECRET}"
    response = requests.post(url, json=payload)
    print(f"[{payload['client_id'][:8]}...] Sent: {payload['events'][0]['name']} | Status: {response.status_code}")

def simulate_session(client_id, purchase_chance=0.2):
    session_id = str(uuid.uuid4().int)[:10]
    user_lang = random.choice(LANGUAGES)
    user_device = random.choice(DEVICES)
    user_country = random.choice(COUNTRIES)
    traffic = weighted_random_traffic_source()

    common_payload = {
        "client_id": client_id,
        "user_properties": {
            "device_category": {"value": user_device},
            "language": {"value": user_lang},
            "geo_country": {"value": user_country},
        }
    }

    session_start_payload = {
        **common_payload,
        "events": [{
            "name": "session_start",
            "params": {
                "session_id": session_id,
                "engagement_time_msec": random.randint(100, 500)
            }
        }]
    }
    send_event(session_start_payload)

    pageview_paths = random.sample(PAGES, random.randint(2, 5))
    for path in pageview_paths:
        event_payload = {
            **common_payload,
            "events": [{
                "name": "page_view",
                "params": {
                    "page_location": f"https://www.lovesdata-test.com{path}",
                    "page_title": path.strip('/').title(),
                    "session_id": session_id,
                    "engagement_time_msec": random.randint(100, 600),
                    "source": traffic['source'],
                    "medium": traffic['medium'],
                    "campaign": traffic.get('campaign', '(not set)')
                }
            }]
        }
        send_event(event_payload)
        time.sleep(random.uniform(0.5, 1.0))

    if random.random() < purchase_chance:
        product = random.choice(PRODUCTS)
        conversion_payload = {
            **common_payload,
            "events": [{
                "name": "purchase",
                "params": {
                    "transaction_id": str(uuid.uuid4()),
                    "currency": "AUD",
                    "value": product["price"],
                    "items": [{
                        "item_id": product["id"],
                        "item_name": product["name"],
                        "price": product["price"],
                        "quantity": 1
                    }],
                    "session_id": session_id
                }
            }]
        }
        send_event(conversion_payload)

def main():
    today = datetime.utcnow().weekday()
    is_weekend = today in [5, 6]

    if is_weekend:
        num_users = random.randint(2, 5)
        session_range = (1, 2)
        purchase_chance = 0.10
        print("Weekend traffic simulation.")
    else:
        num_users = random.randint(8, 20)
        session_range = (1, 3)
        purchase_chance = 0.20
        print("Weekday traffic simulation.")

    sampled_users = random.sample(USER_POOL, num_users)

    for client_id in sampled_users:
        sessions = random.randint(*session_range)
        for _ in range(sessions):
            simulate_session(client_id, purchase_chance)
            time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    main()
