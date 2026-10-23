"""
Geocoding module for FoodBridge AI.
Resolves human-readable addresses to GeoJSON Point coordinates (lat, lng)
and provides reverse geocoding.

Features:
- MongoDB geocode_cache collection with 90-day TTL index to minimize external API hits.
- Rate-limited to max 1 request/second for Nominatim usage compliance.
- User-Agent header: FoodBridgeAI/1.0.
- Swappable provider interface via GEOCODER_PROVIDER env var.
"""

import os
import time
import threading
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import Optional, Tuple

try:
    from database import geocode_cache_collection
except ImportError:
    geocode_cache_collection = None

# Nominatim compliance: strictly max 1 request per second
_nominatim_lock = threading.Lock()
_last_request_time: float = 0.0

DEFAULT_USER_AGENT = "FoodBridgeAI/1.0 (contact: info@foodbridge.platform)"


def _normalize_key(address: str) -> str:
    """Normalizes address string for cache key."""
    return " ".join(address.strip().lower().split())


def _throttle_nominatim() -> None:
    """Enforces 1.0 second delay between consecutive Nominatim requests."""
    global _last_request_time
    with _nominatim_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        _last_request_time = time.time()


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Geocodes an address string to (latitude, longitude).
    Checks MongoDB geocode_cache first. If cache miss, queries geocoder provider.
    Returns (lat, lng) or None if resolution fails.
    """
    if not address or not address.strip():
        return None

    clean_address = address.strip()
    norm_key = _normalize_key(clean_address)

    # 1. Check MongoDB cache
    if geocode_cache_collection is not None:
        try:
            cached = geocode_cache_collection.find_one({"normalizedKey": norm_key})
            if cached and "lat" in cached and "lng" in cached:
                return float(cached["lat"]), float(cached["lng"])
        except Exception as e:
            print(f"[Geocode Cache] Cache lookup error: {e}")

    # 2. Check provider
    provider = os.getenv("GEOCODER_PROVIDER", "nominatim").lower()
    lat_lng: Optional[Tuple[float, float]] = None

    if provider == "mock":
        # Deterministic coordinates for test/mock environments (e.g. Solapur city center)
        lat_lng = (17.6599, 75.9064)
    else:
        # Default: Nominatim OpenStreetMap
        try:
            _throttle_nominatim()
            encoded_query = urllib.parse.quote(clean_address)
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&limit=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": os.getenv("NOMINATIM_USER_AGENT", DEFAULT_USER_AGENT)},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if data and len(data) > 0:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        lat_lng = (lat, lon)
        except Exception as e:
            print(f"[Geocode] External geocoding failed for '{clean_address}': {e}")
            lat_lng = None

    # 3. Store result in cache if found
    if lat_lng and geocode_cache_collection is not None:
        try:
            geocode_cache_collection.update_one(
                {"normalizedKey": norm_key},
                {
                    "$set": {
                        "normalizedKey": norm_key,
                        "address": clean_address,
                        "lat": lat_lng[0],
                        "lng": lat_lng[1],
                        "provider": provider,
                        "createdAt": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            print(f"[Geocode Cache] Cache write error: {e}")

    return lat_lng


def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """
    Reverse geocodes (lat, lng) to a human-readable display address.
    """
    norm_key = f"rev:{round(lat, 4)}:{round(lng, 4)}"

    # Check cache
    if geocode_cache_collection is not None:
        try:
            cached = geocode_cache_collection.find_one({"normalizedKey": norm_key})
            if cached and "display_name" in cached:
                return cached["display_name"]
        except Exception as e:
            print(f"[Geocode Cache] Reverse cache lookup error: {e}")

    provider = os.getenv("GEOCODER_PROVIDER", "nominatim").lower()
    if provider == "mock":
        return "Solapur Central, Maharashtra, India"

    display_name: Optional[str] = None
    try:
        _throttle_nominatim()
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": os.getenv("NOMINATIM_USER_AGENT", DEFAULT_USER_AGENT)},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                display_name = data.get("display_name")
    except Exception as e:
        print(f"[Geocode] External reverse geocoding failed for ({lat}, {lng}): {e}")

    if display_name and geocode_cache_collection is not None:
        try:
            geocode_cache_collection.update_one(
                {"normalizedKey": norm_key},
                {
                    "$set": {
                        "normalizedKey": norm_key,
                        "lat": lat,
                        "lng": lng,
                        "display_name": display_name,
                        "provider": provider,
                        "createdAt": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            print(f"[Geocode Cache] Reverse cache write error: {e}")

    return display_name


def format_geojson_point(lat: float, lng: float) -> dict:
    """Returns a MongoDB GeoJSON Point dictionary [lng, lat]."""
    return {
        "type": "Point",
        "coordinates": [float(lng), float(lat)],
    }
