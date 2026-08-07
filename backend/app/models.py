"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Input for a location search."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude of the starting point")
    lon: float = Field(..., ge=-180, le=180, description="Longitude of the starting point")
    radius_km: float = Field(5.0, gt=0, le=50, description="Search radius in kilometres")

    spacing_m: float | None = Field(
        None, ge=25, le=1000, description="Grid spacing in metres (defaults to the config value)"
    )
    time_profile: str | None = Field(
        None, description="Key from config.time_profiles, e.g. 'weekend_afternoon'"
    )
    max_results: int | None = Field(None, ge=10, le=5000, description="Maximum number of points returned")

    # Partial override of the scoring config, for this request only
    # (e.g. {"total": {"solitude_weight": 0.8}}). Never persisted.
    weights: dict[str, Any] | None = Field(None, description="Partial config override")

    use_strava: bool | None = Field(None, description="Enable or disable the Strava heatmap for this search")


class Warning_(BaseModel):
    level: str
    text: str


class CandidatePoint(BaseModel):
    id: int
    lat: float
    lon: float
    score: float
    solitude: float
    flyability: float
    blocked: bool
    category: str
    category_label: str
    area_name: str = ""
    distances: dict[str, float]
    components: dict[str, dict[str, float]]
    warnings: list[Warning_] = []
    strava: float = 0.0
    population: float | None = None


class SearchStats(BaseModel):
    grid_points: int
    returned_points: int
    spacing_m: float
    radius_km: float
    tiles_total: int = 0
    tiles_cached: int = 0
    tiles_fetched: int = 0
    osm_elements: int = 0
    layers: dict[str, int] = {}
    duration_s: float = 0.0
    score_min: float = 0.0
    score_max: float = 0.0
    score_mean: float = 0.0
    blocked_share: float = 0.0


class SearchResult(BaseModel):
    center: dict[str, float]
    radius_km: float
    time_profile: str
    time_profile_label: str
    points: list[CandidatePoint]
    stats: SearchStats
    notes: list[str] = []


class GeocodeResult(BaseModel):
    label: str
    lat: float
    lon: float
    type: str = ""


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    error: str | None = None
    elapsed_s: float = 0.0
    result: SearchResult | None = None


class ConfigUpdate(BaseModel):
    """A full or partial configuration to be persisted."""

    config: dict[str, Any]
    merge: bool = Field(True, description="True = merge with the existing config, False = replace it")
