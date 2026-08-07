"""
Geometry helpers.

Core idea: we do not work in degrees. Everything is projected once into a local
metric coordinate system (east/north in metres relative to the search centre).
For radii up to ~50 km the error of this equidistant approximation stays below
0.1 %, and in exchange we can use shapely directly with metre distances -
without pulling in pyproj.
"""

from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_M = 6371008.8


class LocalProjection:
    """
    Local, axis-aligned metre projection around a reference point.

    x = east in metres, y = north in metres, origin = (lat0, lon0).
    """

    def __init__(self, lat0: float, lon0: float) -> None:
        self.lat0 = float(lat0)
        self.lon0 = float(lon0)
        phi = math.radians(self.lat0)
        # WGS84 series expansion: metres per degree of latitude/longitude here.
        self.m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
        self.m_per_deg_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
        # Guard against dividing by ~0 near the poles (irrelevant for FPV, but tidy).
        if abs(self.m_per_deg_lon) < 1.0:
            self.m_per_deg_lon = 1.0

    def to_xy(self, lat, lon):
        """(lat, lon) -> (x, y) in metres. Accepts scalars and numpy arrays."""
        lat_arr = np.asarray(lat, dtype=float)
        lon_arr = np.asarray(lon, dtype=float)
        x = (lon_arr - self.lon0) * self.m_per_deg_lon
        y = (lat_arr - self.lat0) * self.m_per_deg_lat
        return x, y

    def to_latlon(self, x, y):
        """(x, y) in metres -> (lat, lon)."""
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        lon = self.lon0 + x_arr / self.m_per_deg_lon
        lat = self.lat0 + y_arr / self.m_per_deg_lat
        return lat, lon

    def bbox_for_radius(self, radius_m: float) -> tuple[float, float, float, float]:
        """
        Enclosing bbox (south, west, north, east) for a radius around the centre.

        Deliberately oversized by 10 % so that objects just outside the radius
        are still found as "nearest object" - otherwise a point on the edge
        would incorrectly look extremely remote.
        """
        pad = radius_m * 1.1
        dlat = pad / self.m_per_deg_lat
        dlon = pad / self.m_per_deg_lon
        return (
            self.lat0 - dlat,
            self.lon0 - dlon,
            self.lat0 + dlat,
            self.lon0 + dlon,
        )


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Exact great-circle distance in metres (for individual checks and tests)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Slippy map tiles (for Strava heatmap sampling)
# ---------------------------------------------------------------------------
def deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Web Mercator tile index (x, y) for a coordinate."""
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    n = 2.0**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def deg2pixel(lat: float, lon: float, zoom: int, tile_size: int = 256) -> tuple[float, float]:
    """Global pixel coordinate (Web Mercator), keeping the fractional part."""
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    n = 2.0**zoom * tile_size
    px = (lon + 180.0) / 360.0 * n
    py = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return px, py
