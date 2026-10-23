"""
Geo matching and logistics module for FoodBridge AI.
Calculates real-world Haversine distances, road distance estimates,
travel ETA, and deterministic receiver-donation match percentages.
"""

import math
import os
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

# Defaults
DEFAULT_MATCH_RADIUS_KM = 25.0
DEFAULT_URBAN_SPEED_KMH = 25.0
DEFAULT_ROAD_CIRCUITY_FACTOR = 1.3  # Urban road distance multiplier over straight-line
CIRCUITY_FACTOR = DEFAULT_ROAD_CIRCUITY_FACTOR
AVERAGE_URBAN_SPEED_KMH = DEFAULT_URBAN_SPEED_KMH


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculates great-circle distance between two geographic coordinates
    using the Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_directions_url(
    dest_lat: float,
    dest_lng: float,
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
) -> str:
    """Generates a universal Google Maps directions URL."""
    if origin_lat is not None and origin_lng is not None:
        return f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}"
    return f"https://www.google.com/maps/dir/?api=1&destination={dest_lat},{dest_lng}"


def calculate_match_metrics(
    receiver_lat: float,
    receiver_lng: float,
    donation_lat: float,
    donation_lng: float,
    pickup_deadline: Optional[datetime] = None,
    match_radius_km: Optional[float] = None,
    urban_speed_kmh: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculates distance, estimated road travel time, time feasibility,
    and match percentage between receiver organization and food donation.
    """
    radius = match_radius_km or float(os.getenv("MATCH_RADIUS_KM", DEFAULT_MATCH_RADIUS_KM))
    speed = urban_speed_kmh or float(os.getenv("AVERAGE_URBAN_SPEED_KMH", DEFAULT_URBAN_SPEED_KMH))

    straight_line_km = calculate_haversine_distance(
        receiver_lat, receiver_lng, donation_lat, donation_lng
    )

    # Urban road circuity factor
    road_distance_km = straight_line_km * DEFAULT_ROAD_CIRCUITY_FACTOR
    estimated_travel_minutes = (road_distance_km / max(speed, 5.0)) * 60.0

    # Deterministic distance match score: 100% at 0 km, 0% at match_radius_km
    distance_score = max(0.0, 1.0 - (road_distance_km / radius))
    match_percent = round(100.0 * distance_score)

    feasible = True
    feasibility_reason = None

    if pickup_deadline is not None:
        if pickup_deadline.tzinfo is None:
            deadline_utc = pickup_deadline.replace(tzinfo=timezone.utc)
        else:
            deadline_utc = pickup_deadline.astimezone(timezone.utc)

        now_utc = datetime.now(timezone.utc)
        minutes_remaining = (deadline_utc - now_utc).total_seconds() / 60.0

        if minutes_remaining <= 0:
            feasible = False
            match_percent = 0
            feasibility_reason = "Pickup deadline has already passed."
        elif estimated_travel_minutes > minutes_remaining:
            feasible = False
            match_percent = 0
            feasibility_reason = (
                f"Cannot reach before pickup deadline (ETA: {round(estimated_travel_minutes)} min, "
                f"remaining: {round(minutes_remaining)} min)."
            )

    directions_url = get_directions_url(
        dest_lat=donation_lat,
        dest_lng=donation_lng,
        origin_lat=receiver_lat,
        origin_lng=receiver_lng,
    )

    return {
        "straightLineDistanceKm": round(straight_line_km, 2),
        "roadDistanceKm": round(road_distance_km, 2),
        "distanceKm": round(road_distance_km, 1),
        "estimatedTravelMinutes": max(1, round(estimated_travel_minutes)),
        "matchPercent": match_percent,
        "feasible": feasible,
        "feasibilityReason": feasibility_reason,
        "directionsUrl": directions_url,
    }
