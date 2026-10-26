"""
Scoring curves.

Every function maps a physical quantity (usually a distance in metres) onto a
score in 0..1, where 1 always means "good". They all operate vectorised on
numpy arrays.
"""

from __future__ import annotations

import numpy as np


def smoothstep(t: np.ndarray) -> np.ndarray:
    """Smooth 0->1 blend (C1 continuous). Expects t already clipped to 0..1."""
    return t * t * (3.0 - 2.0 * t)


def ramp(values: np.ndarray, critical: float, ideal: float) -> np.ndarray:
    """
    Rising ramp: at or below ``critical`` yields 0, at or above ``ideal`` yields 1.

    Typical use: "distance to buildings" - 80 m is bad (0), 500 m is ideal (1),
    with a smooth transition in between.
    """
    values = np.asarray(values, dtype=float)
    if ideal <= critical:
        # Degenerate configuration: hard step instead of dividing by zero.
        return (values >= ideal).astype(float)
    t = np.clip((values - critical) / (ideal - critical), 0.0, 1.0)
    return smoothstep(t)


def inverse_ramp(values: np.ndarray, critical: float, ideal: float) -> np.ndarray:
    """Falling ramp: at or below ``critical`` yields 1, at or above ``ideal`` yields 0."""
    return 1.0 - ramp(values, critical, ideal)


def bump(values: np.ndarray, peak_near: float, peak_far: float, fade: float) -> np.ndarray:
    """
    Plateau curve for the nearby-structure bonus.

    0 right at the object (that is where you are standing), 1 in the window
    between ``peak_near`` and ``peak_far``, then falling off towards ``fade`` -
    a bare field with nothing to fly around scores lower again.
    """
    values = np.asarray(values, dtype=float)
    rising = ramp(values, 0.0, max(peak_near, 1e-6))
    falling = inverse_ramp(values, peak_far, max(fade, peak_far + 1e-6))
    return np.minimum(rising, falling)


def log_density_score(density: np.ndarray, max_density: float) -> np.ndarray:
    """
    Population density (inhabitants per km^2) -> score.

    Logarithmic, because the difference between 0 and 50 inhabitants/km^2
    matters far more to us than the one between 2000 and 2050.
    """
    density = np.clip(np.asarray(density, dtype=float), 0.0, None)
    max_density = max(float(max_density), 1.0)
    normalized = np.log1p(density) / np.log1p(max_density)
    return np.clip(1.0 - normalized, 0.0, 1.0)


def weighted_mean(components: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    """
    Weighted mean across score components.

    Weights are normalised automatically, so individual components can be set
    to 0 in the config without having to rebalance the rest.
    """
    total_weight = 0.0
    accumulator: np.ndarray | None = None
    for name, values in components.items():
        w = float(weights.get(name, 0.0))
        if w <= 0.0:
            continue
        contribution = np.asarray(values, dtype=float) * w
        accumulator = contribution if accumulator is None else accumulator + contribution
        total_weight += w
    if accumulator is None or total_weight <= 0.0:
        # No active component -> neutral score.
        any_array = next(iter(components.values()), np.zeros(0))
        return np.full(np.asarray(any_array).shape, 0.5)
    return np.clip(accumulator / total_weight, 0.0, 1.0)
