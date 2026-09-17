"""Spatial helper: Gazetteer matching and vertex-to-vertex Haversine distance."""

import json
import math
import os
from pathlib import Path


def haversine_distance_meters(coord1: list[float], coord2: list[float]) -> float:
    """
    Calculate the great-circle distance between two points on Earth in meters.
    Coordinates are [longitude, latitude].
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    # Radius of Earth in meters
    r = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return r * c


def find_default_geojson() -> str:
    """Finds gazetteer.geojson relative to repo root or current file."""
    # Try relative to current file traversing upwards
    current = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = current / "data" / "gazetteer.geojson"
        if candidate.is_file():
            return str(candidate)
        current = current.parent

    # Fallback to local ./data/gazetteer.geojson
    return "data/gazetteer.geojson"


class Gazetteer:
    def __init__(self, geojson_path: str = None):
        if geojson_path is None:
            geojson_path = find_default_geojson()

        with open(geojson_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.features_by_id = {}
        self.alias_map = {}

        for feature in self.data.get("features", []):
            road_id = feature["properties"]["id"]
            name = feature["properties"]["name"]
            self.features_by_id[road_id] = feature

            # Map main name
            self.alias_map[name.lower().strip()] = road_id

            # Map aliases
            for alias in feature["properties"].get("aliases", []):
                self.alias_map[alias.lower().strip()] = road_id

    def match_road(self, road_text: str) -> str | None:
        """Find the matching road_id for a given string from the tender."""
        if not road_text:
            return None

        clean = road_text.lower().strip()

        # 1. Direct match
        if clean in self.alias_map:
            return self.alias_map[clean]

        # 2. Substring containment match
        for alias, road_id in self.alias_map.items():
            if alias in clean or clean in alias:
                return road_id

        return None

    def get_spatial_relationship(self, road_id_a: str, road_id_b: str, threshold_meters: float = 250.0) -> str:
        """
        Determines spatial relationship between two roads:
        - "SAME": identical road IDs
        - "NEARBY": minimum distance between any vertex <= threshold_meters
        - "NONE": farther than threshold_meters
        """
        if not road_id_a or not road_id_b:
            return "NONE"

        if road_id_a == road_id_b:
            return "SAME"

        feat_a = self.features_by_id.get(road_id_a)
        feat_b = self.features_by_id.get(road_id_b)

        if not feat_a or not feat_b:
            return "NONE"

        coords_a = feat_a["geometry"]["coordinates"]
        coords_b = feat_b["geometry"]["coordinates"]

        min_dist = float("inf")
        for pt_a in coords_a:
            for pt_b in coords_b:
                dist = haversine_distance_meters(pt_a, pt_b)
                if dist < min_dist:
                    min_dist = dist
                    if min_dist <= threshold_meters:
                        return "NEARBY"

        return "NEARBY" if min_dist <= threshold_meters else "NONE"
