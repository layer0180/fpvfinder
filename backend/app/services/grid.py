"""
Generates the candidate points inside the search radius.

Uses a staggered (hexagonal) grid: for the same number of points it covers the
area more evenly than a square grid, which means small good spots are found
more reliably.
"""

from __future__ import annotations

import math

import numpy as np


def adaptive_spacing(radius_m: float, spacing_m: float, max_points: int) -> float:
    """
    Widens the grid spacing if the radius would otherwise produce too many points.

    Rough estimate: point count ~ circle area / cell area.
    """
    if max_points <= 0:
        return spacing_m
    estimated = math.pi * radius_m**2 / (spacing_m**2 * 0.866)  # 0.866 = hex packing factor
    if estimated <= max_points:
        return spacing_m
    factor = math.sqrt(estimated / max_points)
    return spacing_m * factor


def build_grid(radius_m: float, spacing_m: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Staggered grid inside the circle.

    Returns: (x, y) in metres relative to the centre.
    """
    spacing_m = max(float(spacing_m), 1.0)
    row_height = spacing_m * math.sqrt(3.0) / 2.0
    n_rows = int(math.ceil(radius_m / row_height))

    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []

    for row in range(-n_rows, n_rows + 1):
        y = row * row_height
        # Half a cell width on every other row -> hexagonal arrangement.
        offset = (spacing_m / 2.0) if (row % 2) else 0.0
        # Only go as far out as the circle reaches at this height.
        half_width_sq = radius_m**2 - y**2
        if half_width_sq <= 0:
            continue
        half_width = math.sqrt(half_width_sq)
        n_cols = int(math.floor((half_width + offset) / spacing_m))
        if n_cols < 0:
            continue
        col_idx = np.arange(-n_cols - 1, n_cols + 2)
        x = col_idx * spacing_m + offset
        keep = x**2 + y**2 <= radius_m**2
        if not np.any(keep):
            continue
        xs.append(x[keep])
        ys.append(np.full(int(keep.sum()), y))

    if not xs:
        return np.zeros(1), np.zeros(1)  # tiny radius: at least return the centre
    return np.concatenate(xs), np.concatenate(ys)
