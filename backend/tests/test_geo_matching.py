import pytest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from geo_matching import (
    calculate_haversine_distance,
    calculate_match_metrics,
    get_directions_url,
    CIRCUITY_FACTOR,
    AVERAGE_URBAN_SPEED_KMH,
)


def test_calculate_haversine_distance():
    # Solapur center (17.6599, 75.9064) to a point ~2.2 km away (17.6799, 75.9064)
    dist = calculate_haversine_distance(17.6599, 75.9064, 17.6799, 75.9064)
    assert 2.0 <= dist <= 2.5

    # Same location should yield 0.0 distance
    zero_dist = calculate_haversine_distance(17.6599, 75.9064, 17.6599, 75.9064)
    assert zero_dist == 0.0


def test_calculate_match_metrics_close_feasible():
    # 2 km straight line -> ~2.6 km road distance
    lat1, lng1 = 17.6599, 75.9064
    lat2, lng2 = 17.6780, 75.9064

    # Deadline 3 hours in the future
    deadline = datetime.now(timezone.utc) + timedelta(hours=3)

    metrics = calculate_match_metrics(lat1, lng1, lat2, lng2, pickup_deadline=deadline)

    assert metrics["straightLineDistanceKm"] > 0
    assert metrics["roadDistanceKm"] == pytest.approx(metrics["straightLineDistanceKm"] * CIRCUITY_FACTOR, abs=0.05)
    assert metrics["estimatedTravelMinutes"] > 0
    assert metrics["feasible"] is True
    assert metrics["matchPercent"] > 80  # very close distance should score high
    assert metrics["directionsUrl"] is not None
    assert "google.com/maps/dir" in metrics["directionsUrl"]


def test_calculate_match_metrics_deadline_expired():
    lat1, lng1 = 17.6599, 75.9064
    lat2, lng2 = 17.6780, 75.9064

    # Deadline was 30 minutes ago
    expired_deadline = datetime.now(timezone.utc) - timedelta(minutes=30)

    metrics = calculate_match_metrics(lat1, lng1, lat2, lng2, pickup_deadline=expired_deadline)

    assert metrics["feasible"] is False
    assert metrics["matchPercent"] == 0
    assert "passed" in metrics["feasibilityReason"].lower()


def test_calculate_match_metrics_far_distance_zero_score():
    # Distance over 30 km (beyond standard 25 km threshold)
    lat1, lng1 = 17.6599, 75.9064
    lat2, lng2 = 17.9599, 75.9064

    metrics = calculate_match_metrics(lat1, lng1, lat2, lng2)

    assert metrics["roadDistanceKm"] > 25.0
    assert metrics["matchPercent"] == 0  # clipped at 0


def test_get_directions_url():
    url = get_directions_url(dest_lat=17.6800, dest_lng=75.9200, origin_lat=17.6599, origin_lng=75.9064)
    assert "https://www.google.com/maps/dir/?api=1" in url
    assert "origin=17.6599,75.9064" in url
    assert "destination=17.68,75.92" in url
