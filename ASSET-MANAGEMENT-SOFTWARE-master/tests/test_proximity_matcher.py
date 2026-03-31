"""Unit tests for tools/processors/equipment_proximity_matcher.py — G-08 D-5."""

import math
import pytest

from tools.processors.equipment_proximity_matcher import (
    EquipmentMatch,
    ProximityMatcher,
    _haversine_m,
    get_proximity_matcher,
    HIGH_CONFIDENCE_RADIUS_M,
    MEDIUM_CONFIDENCE_RADIUS_M,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

BASE_LAT = 33.2600
BASE_LON = -8.5100


def _offset(lat: float, lon: float, dist_m: float, bearing_deg: float):
    """Return WGS-84 point offset by dist_m in bearing_deg direction."""
    R = 6_371_000.0
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(dist_m / R)
        + math.cos(lat1) * math.sin(dist_m / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(dist_m / R) * math.cos(lat1),
        math.cos(dist_m / R) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def _registry(*items):
    """Build an equipment registry list from (tag, lat, lon) tuples."""
    return [
        {"equipment_tag": t, "equipment_id": f"id-{t}", "name": f"Name {t}", "gps_lat": lat, "gps_lon": lon}
        for t, lat, lon in items
    ]


# ── Haversine tests ───────────────────────────────────────────────────────────

class TestHaversine:
    def test_zero_distance(self):
        assert _haversine_m(BASE_LAT, BASE_LON, BASE_LAT, BASE_LON) == pytest.approx(0.0)

    def test_known_distance(self):
        # 10 m north at equator: Δlat = 10/111_111 deg ≈ 0.00009
        d = _haversine_m(0.0, 0.0, 10 / 111_111, 0.0)
        assert d == pytest.approx(10.0, rel=0.01)

    def test_symmetry(self):
        a = _haversine_m(33.26, -8.51, 33.28, -8.49)
        b = _haversine_m(33.28, -8.49, 33.26, -8.51)
        assert a == pytest.approx(b, rel=1e-9)

    def test_approximately_500m(self):
        lat2, lon2 = _offset(BASE_LAT, BASE_LON, 500, 0)
        d = _haversine_m(BASE_LAT, BASE_LON, lat2, lon2)
        assert d == pytest.approx(500, rel=0.01)


# ── ProximityMatcher unit tests ───────────────────────────────────────────────

class TestInit:
    def test_default_radii(self):
        m = ProximityMatcher()
        assert m._high_r == HIGH_CONFIDENCE_RADIUS_M
        assert m._medium_r == MEDIUM_CONFIDENCE_RADIUS_M

    def test_invalid_negative_radius_raises(self):
        with pytest.raises(ValueError):
            ProximityMatcher(high_radius_m=-1, medium_radius_m=100)

    def test_high_ge_medium_raises(self):
        with pytest.raises(ValueError):
            ProximityMatcher(high_radius_m=100, medium_radius_m=20)


class TestFindNearby:
    def test_returns_empty_when_no_nodes_with_gps(self):
        m = ProximityMatcher()
        registry = [{"equipment_tag": "TAG-001", "equipment_id": "id-001", "name": "Pump"}]
        result = m.find_nearby(BASE_LAT, BASE_LON, registry)
        assert result == []

    def test_skips_nodes_without_gps(self):
        m = ProximityMatcher()
        registry = [
            {"equipment_tag": "A", "equipment_id": "a", "name": "", "gps_lat": None, "gps_lon": BASE_LON},
            {"equipment_tag": "B", "equipment_id": "b", "name": "", "gps_lat": BASE_LAT, "gps_lon": None},
        ]
        assert m.find_nearby(BASE_LAT, BASE_LON, registry) == []

    def test_high_confidence_within_20m(self):
        lat2, lon2 = _offset(BASE_LAT, BASE_LON, 10, 90)
        reg = _registry(("PUMP-001", lat2, lon2))
        m = ProximityMatcher()
        matches = m.find_nearby(BASE_LAT, BASE_LON, reg)
        assert len(matches) == 1
        assert matches[0].confidence == "HIGH"
        assert matches[0].distance_m < 20

    def test_medium_confidence_between_20_and_100m(self):
        lat2, lon2 = _offset(BASE_LAT, BASE_LON, 60, 0)
        reg = _registry(("PUMP-002", lat2, lon2))
        m = ProximityMatcher()
        matches = m.find_nearby(BASE_LAT, BASE_LON, reg)
        assert len(matches) == 1
        assert matches[0].confidence == "MEDIUM"

    def test_excludes_nodes_beyond_radius(self):
        lat2, lon2 = _offset(BASE_LAT, BASE_LON, 200, 0)
        reg = _registry(("FAR-001", lat2, lon2))
        m = ProximityMatcher()
        matches = m.find_nearby(BASE_LAT, BASE_LON, reg)
        assert len(matches) == 0

    def test_sorted_by_distance_ascending(self):
        lat_10, lon_10 = _offset(BASE_LAT, BASE_LON, 10, 0)
        lat_50, lon_50 = _offset(BASE_LAT, BASE_LON, 50, 0)
        lat_90, lon_90 = _offset(BASE_LAT, BASE_LON, 90, 0)
        reg = _registry(
            ("FAR", lat_90, lon_90),
            ("NEAR", lat_10, lon_10),
            ("MID", lat_50, lon_50),
        )
        m = ProximityMatcher()
        matches = m.find_nearby(BASE_LAT, BASE_LON, reg)
        distances = [match.distance_m for match in matches]
        assert distances == sorted(distances)
        assert matches[0].equipment_tag == "NEAR"

    def test_custom_radius_filters_correctly(self):
        lat_30, lon_30 = _offset(BASE_LAT, BASE_LON, 30, 0)
        lat_80, lon_80 = _offset(BASE_LAT, BASE_LON, 80, 0)
        reg = _registry(("A", lat_30, lon_30), ("B", lat_80, lon_80))
        m = ProximityMatcher()
        matches_50 = m.find_nearby(BASE_LAT, BASE_LON, reg, radius_m=50)
        assert len(matches_50) == 1
        assert matches_50[0].equipment_tag == "A"

    def test_multiple_nodes_all_returned_in_radius(self):
        positions = [_offset(BASE_LAT, BASE_LON, d, angle) for d, angle in [(5, 0), (15, 90), (40, 180), (90, 270)]]
        reg = _registry(*[(f"EQ-{i}", lat, lon) for i, (lat, lon) in enumerate(positions)])
        m = ProximityMatcher()
        matches = m.find_nearby(BASE_LAT, BASE_LON, reg)
        assert len(matches) == 4

    def test_equipment_tag_from_tag_field(self):
        lat2, lon2 = _offset(BASE_LAT, BASE_LON, 5, 0)
        reg = [{"equipment_tag": "TAG-VIA-FIELD", "equipment_id": "x", "name": "X", "gps_lat": lat2, "gps_lon": lon2}]
        m = ProximityMatcher()
        assert m.find_nearby(BASE_LAT, BASE_LON, reg)[0].equipment_tag == "TAG-VIA-FIELD"


class TestBestMatch:
    def test_returns_none_when_no_match(self):
        m = ProximityMatcher()
        assert m.best_match(BASE_LAT, BASE_LON, []) is None

    def test_returns_closest(self):
        lat_5, lon_5 = _offset(BASE_LAT, BASE_LON, 5, 0)
        lat_50, lon_50 = _offset(BASE_LAT, BASE_LON, 50, 0)
        reg = _registry(("FAR", lat_50, lon_50), ("NEAR", lat_5, lon_5))
        m = ProximityMatcher()
        best = m.best_match(BASE_LAT, BASE_LON, reg)
        assert best is not None
        assert best.equipment_tag == "NEAR"


class TestFactory:
    def test_get_proximity_matcher_returns_instance(self):
        matcher = get_proximity_matcher()
        assert isinstance(matcher, ProximityMatcher)
