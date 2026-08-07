"""Human-readable labels for the UI (categories, score components, distances)."""

from __future__ import annotations

CATEGORY_LABELS: dict[str, str] = {
    "farmland": "Arable field", "farmyard": "Farmyard", "meadow": "Meadow", "grass": "Grass",
    "grassland": "Grassland", "orchard": "Orchard", "vineyard": "Vineyard",
    "greenhouse": "Greenhouse", "plant_nursery": "Plant nursery", "forest": "Forest",
    "scrub": "Scrub", "heath": "Heath", "wetland": "Wetland", "moor": "Moor",
    "water": "Water", "beach": "Beach / sand", "brownfield": "Brownfield",
    "greenfield": "Undeveloped land", "construction": "Construction site", "quarry": "Quarry",
    "landfill": "Landfill", "industrial": "Industrial estate", "commercial": "Commercial area",
    "retail": "Retail area", "railway_area": "Railway land", "military": "Military area",
    "residential": "Residential area", "village_green": "Village green",
    "school_grounds": "School / hospital grounds", "cemetery": "Cemetery",
    "religious": "Religious grounds", "park": "Park", "garden": "Garden",
    "allotments": "Allotments", "playground": "Playground", "pitch": "Sports pitch",
    "sports_centre": "Sports centre", "golf_course": "Golf course",
    "recreation_ground": "Recreation ground", "camp_site": "Camp site", "dog_park": "Dog park",
    "marina": "Marina", "nature_reserve": "Nature reserve", "protected_area": "Protected area",
    "national_park": "National park", "aerodrome": "Aerodrome", "unknown": "Unmapped",
}

COMPONENT_LABELS: dict[str, str] = {
    # Solitude
    "buildings": "Distance to buildings",
    "residential": "Distance to residential / recreation",
    "roads": "Distance to roads",
    "paths": "Distance to paths",
    "attractors": "Distance to crowd magnets",
    "landuse": "Land use",
    "strava": "Strava activity here",
    "strava_distance": "Distance to busy routes",
    "population": "Population density",
    # Flyability
    "openness": "Open terrain",
    "takeoff": "Take-off / landing spot",
    "roads_safety": "Road safety clearance",
    "railway": "Railway safety clearance",
    "powerlines": "Distance to power lines",
    "structure": "Nearby structure",
}

DISTANCE_LABELS: dict[str, str] = {
    "d_building": "Nearest building",
    "d_building_res": "Nearest dwelling",
    "d_settlement": "Residential / recreation area",
    "d_road": "Nearest road",
    "d_path": "Nearest path",
    "d_railway": "Railway line",
    "d_power": "Power line / pylon",
    "d_attractor": "Crowd magnet",
    "d_tree": "Tree cover",
    "d_water": "Water",
    "d_aerodrome": "Aerodrome",
    "d_protected": "Protected area",
    "d_strava": "Nearest busy route",
}
