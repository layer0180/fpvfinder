"""
Offline smoke test of the scoring pipeline - no network access.

Builds a small synthetic world (a village, an arable field, a forest, a road,
a playground) and checks that the resulting scores are plausible.

Run it from the ``backend`` directory:
    .venv\\Scripts\\python.exe -m tests.test_scoring_offline
or with pytest:
    .venv\\Scripts\\python.exe -m pytest tests
"""

from __future__ import annotations

import numpy as np

from app.config import get_config
from app.scoring.aggregate import apply_hard_rules, build_warnings, combine_scores
from app.scoring.features import compute_features
from app.scoring.flyability import score_flyability
from app.scoring.solitude import score_solitude
from app.services.grid import build_grid
from app.services.osm_layers import build_layers
from app.services.spatial import LocalProjection

CENTER_LAT, CENTER_LON = 48.700, 9.150


def _offset(d_north_m: float, d_east_m: float) -> tuple[float, float]:
    """Helper: metre offset -> (lat, lon)."""
    proj = LocalProjection(CENTER_LAT, CENTER_LON)
    lat, lon = proj.to_latlon(d_east_m, d_north_m)
    return float(lat), float(lon)


def _ring(center_n: float, center_e: float, half_m: float) -> list[dict[str, float]]:
    """A square ring as an Overpass ``geometry`` list."""
    corners = [
        (center_n - half_m, center_e - half_m),
        (center_n - half_m, center_e + half_m),
        (center_n + half_m, center_e + half_m),
        (center_n + half_m, center_e - half_m),
        (center_n - half_m, center_e - half_m),
    ]
    out = []
    for n, e in corners:
        lat, lon = _offset(n, e)
        out.append({"lat": lat, "lon": lon})
    return out


def build_fake_elements() -> list[dict]:
    """Synthetic world: village to the west, field in the middle, forest to the east."""
    elements: list[dict] = []

    # Residential area 2 km west
    elements.append(
        {"type": "way", "id": 1, "tags": {"landuse": "residential"}, "geometry": _ring(0, -2000, 400)}
    )
    # 30 houses inside it
    for i in range(30):
        lat, lon = _offset(-300 + i * 20, -2000 + (i % 5) * 60)
        elements.append(
            {"type": "way", "id": 100 + i, "tags": {"building": "house"}, "center": {"lat": lat, "lon": lon}}
        )
    # Arable field in the middle (2 km across)
    elements.append({"type": "way", "id": 2, "tags": {"landuse": "farmland"}, "geometry": _ring(0, 0, 1000)})
    # Forest to the east
    elements.append({"type": "way", "id": 3, "tags": {"natural": "wood"}, "geometry": _ring(0, 2000, 700)})
    # Country road running north to south at x = -800 m
    road = [_offset(n, -800) for n in range(-2000, 2001, 200)]
    elements.append(
        {
            "type": "way",
            "id": 4,
            "tags": {"highway": "secondary", "name": "Test Road"},
            "geometry": [{"lat": la, "lon": lo} for la, lo in road],
        }
    )
    # Farm track crossing the field
    track = [_offset(0, e) for e in range(-1000, 1001, 200)]
    elements.append(
        {
            "type": "way",
            "id": 5,
            "tags": {"highway": "track"},
            "geometry": [{"lat": la, "lon": lo} for la, lo in track],
        }
    )
    # Playground at the edge of the village
    lat, lon = _offset(0, -1500)
    elements.append({"type": "node", "id": 6, "tags": {"leisure": "playground"}, "lat": lat, "lon": lon})
    # Power line to the north-east
    power = [_offset(1200, e) for e in range(0, 2001, 400)]
    elements.append(
        {
            "type": "way",
            "id": 7,
            "tags": {"power": "line"},
            "geometry": [{"lat": la, "lon": lo} for la, lo in power],
        }
    )
    # Nature reserve to the south
    elements.append(
        {
            "type": "way",
            "id": 8,
            "tags": {"leisure": "nature_reserve", "name": "Test Reserve", "protect_class": "4"},
            "geometry": _ring(-2200, 0, 500),
        }
    )
    return elements


def run() -> dict:
    config = get_config()
    proj = LocalProjection(CENTER_LAT, CENTER_LON)
    layers = build_layers(build_fake_elements(), proj, config)

    px, py = build_grid(radius_m=3000, spacing_m=150)
    features = compute_features(layers, px, py)

    solitude, sol_comp = score_solitude(features, config, recreation=1.0, agriculture=0.35)
    flyability, fly_comp = score_flyability(features, config)
    blocked = apply_hard_rules(features, config)
    total = combine_scores(solitude, flyability, blocked, config)

    return {
        "layers": layers.summary(),
        "n_points": len(px),
        "px": px, "py": py,
        "features": features,
        "solitude": solitude,
        "flyability": flyability,
        "blocked": blocked,
        "total": total,
        "config": config,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_layers_parsed():
    r = run()
    assert r["layers"]["buildings"] == 30
    assert r["layers"]["roads"] == 1
    assert r["layers"]["paths"] == 1
    assert r["layers"]["areas"] >= 4
    assert r["layers"]["protected"] == 1
    assert r["layers"]["attractors"] == 1


def test_field_beats_village():
    """The middle of the field must score far better than the village."""
    r = run()
    px, py, total = r["px"], r["py"], r["total"]
    field = int(np.argmin((px - 600) ** 2 + (py - 600) ** 2))       # open field
    village = int(np.argmin((px + 2000) ** 2 + (py - 0) ** 2))       # village centre
    assert total[field] > total[village] + 0.3, (total[field], total[village])
    assert r["blocked"][village]
    assert not r["blocked"][field]


def test_protected_area_blocked():
    r = run()
    px, py = r["px"], r["py"]
    inside = int(np.argmin((px - 0) ** 2 + (py + 2200) ** 2))
    assert r["features"]["in_protected"][inside]
    assert r["blocked"][inside]


def test_powerline_lowers_flyability():
    r = run()
    px, py = r["px"], r["py"]
    near_line = int(np.argmin((px - 800) ** 2 + (py - 1200) ** 2))
    far_line = int(np.argmin((px - 800) ** 2 + (py - 0) ** 2))
    assert r["flyability"][near_line] < r["flyability"][far_line]


def test_warnings_are_generated():
    r = run()
    px, py = r["px"], r["py"]
    near_road = int(np.argmin((px + 800) ** 2 + (py - 500) ** 2))
    warnings = build_warnings(r["features"], near_road, r["config"])
    assert any("Road" in w["text"] for w in warnings), warnings


if __name__ == "__main__":
    r = run()
    px, py, total = r["px"], r["py"], r["total"]
    print("Layers:", r["layers"])
    print(f"Grid points: {r['n_points']}")
    print(f"Score  min/mean/max: {total.min():.3f} / {total.mean():.3f} / {total.max():.3f}")
    print(f"Blocked: {r['blocked'].mean() * 100:.1f} %")

    best = int(np.argmax(total))
    print(f"\nBest point: x={px[best]:.0f} m, y={py[best]:.0f} m, score {total[best]:.3f}")
    print(f"  land use: {r['features']['category'][best]}")
    print(f"  solitude {r['solitude'][best]:.3f} | flyability {r['flyability'][best]:.3f}")
    for key in ("d_building", "d_settlement", "d_road", "d_path", "d_power", "d_tree"):
        print(f"  {key}: {r['features'][key][best]:.0f} m")
    for w in build_warnings(r["features"], best, r["config"]):
        print(f"  [{w['level']}] {w['text']}")

    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {name}")
