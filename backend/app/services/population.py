"""
Optional integration of a population density raster (GHSL / WorldPop).

Usage:
  1. Obtain a GeoTIFF, for example
     - GHSL GHS-POP (https://human-settlement.emergency.copernicus.eu/download.php)
     - WorldPop (https://www.worldpop.org/)
  2. Put the file at ``backend/data/population.tif``
     (a different path can be set via ``population.raster_path`` in weights.json)
  3. ``pip install rasterio``

The component then enables itself (see config._auto_enable_optional_sources).
Without the file or rasterio this module returns NaN and the component is
ignored.

Watch the units: GHS-POP reports inhabitants per cell (e.g. 100 m by 100 m),
not per km^2. ``cell_area_km2`` converts that - please match it to your raster.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.config import BACKEND_DIR


class PopulationRaster:
    """Thin wrapper around rasterio - opens the raster exactly once."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config.get("population", {})
        self.path = BACKEND_DIR / str(self.cfg.get("raster_path", "data/population.tif"))
        self.available = False
        self.error: str | None = None
        self._dataset = None
        self._warp_transform = None

        if not bool(self.cfg.get("enabled")):
            return
        if not Path(self.path).exists():
            self.error = f"Raster not found: {self.path}"
            return
        try:
            import rasterio
            from rasterio.warp import transform as warp_transform

            self._dataset = rasterio.open(self.path)
            self._warp_transform = warp_transform
            self.available = True
        except ImportError:
            self.error = "rasterio is not installed (pip install rasterio)."
        except Exception as exc:  # rasterio raises its own error types
            self.error = f"Could not read the raster: {exc}"

    def sample(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """
        Density values for all points; NaN when unavailable.

        Returned in inhabitants per km^2.
        """
        n = len(lats)
        if not self.available or self._dataset is None or n == 0:
            return np.full(n, np.nan)

        try:
            # Transform coordinates into the raster CRS (GHSL uses Mollweide!).
            xs, ys = self._warp_transform("EPSG:4326", self._dataset.crs, lons.tolist(), lats.tolist())
            values = np.array(
                [v[0] for v in self._dataset.sample(zip(xs, ys), indexes=1)],
                dtype=float,
            )
        except Exception as exc:
            self.error = f"Sampling failed: {exc}"
            return np.full(n, np.nan)

        nodata = self._dataset.nodata
        if nodata is not None:
            values = np.where(values == nodata, 0.0, values)
        values = np.where(values < 0, 0.0, values)

        cell_area_km2 = float(self.cfg.get("cell_area_km2", 0.01))  # default: 100 m grid
        if cell_area_km2 > 0:
            values = values / cell_area_km2
        return values

    def close(self) -> None:
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None
