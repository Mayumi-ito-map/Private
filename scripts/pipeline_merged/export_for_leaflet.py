"""
export_for_leaflet（合体Excel版）

司令塔①②の結果を Leaflet 地図用 GeoJSON に変換。
入力: output_match_results/*.xlsx（優先）、output_match_name/*.xlsx
出力: output_leaflet/
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ast
import json
import math
import pandas as pd
from utils import is_excel_lock_file

BASE_DIR = PROJECT_ROOT
OUTPUT_MATCH_NAME_DIR = BASE_DIR / "output_match_name"
OUTPUT_MATCH_RESULTS_DIR = BASE_DIR / "output_match_results"
OUTPUT_LEAFLET_DIR = BASE_DIR / "output_leaflet"

COLOR_LOCAL = "#0000ff"
COLOR_GEONAMES = "#ff0000"


def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_candidates(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s in ("None", "nan", "[]"):
            return []
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return parsed
            return [parsed] if isinstance(parsed, dict) else []
        except (ValueError, SyntaxError):
            return []
    return []


def row_candidates(row):
    judge = str(row.get("judge", row.get("name_judge", ""))).strip()
    if judge != "0":
        return parse_candidates(row.get("geonames_hits", row.get("geonames_name_hits")))
    for col in (
        "stage1-hit-1",
        "stage1-hit-2+",
        "stage2-hit-1",
        "stage2-hit-2+",
        "stage3-hit-1",
        "stage3-hit-2+",
        "Stage1_hit",
        "Stage2_hit",
        "Stage3_hit",
    ):
        hits = parse_candidates(row.get(col))
        if hits:
            return hits
    return []


def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def build_geojson_for_country(df, country_code, country_label):
    features = []
    for idx, row in df.iterrows():
        original_row = int(idx) + 1
        local_lat = safe_float(row.get("local_lat"))
        local_lon = safe_float(row.get("local_lon"))
        name_local = str(row.get("修正後欧文地名", row.get("normalized_candidates", "")))[:200]
        candidates = row_candidates(row)

        if local_lat is not None and local_lon is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [local_lon, local_lat]},
                "properties": {"type": "Local", "name": name_local, "original_row": original_row, "marker-color": COLOR_LOCAL},
            })

        for c in candidates:
            gid = c.get("geonameid") or c.get("id")
            lat = safe_float(c.get("lat"))
            lon = safe_float(c.get("lon"))
            if lat is None or lon is None:
                continue
            name_gn = str(c.get("name", ""))[:200]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "type": "GeoNames", "id": str(gid), "country": country_code,
                    "original_row": original_row, "marker-color": COLOR_GEONAMES,
                    "name": name_gn, "fcode": c.get("fcode", ""), "fcl": c.get("fcl", ""),
                },
            })
            if local_lat is not None and local_lon is not None:
                distance_km = haversine_km(local_lon, local_lat, lon, lat)
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[local_lon, local_lat], [lon, lat]]},
                    "properties": {"type": "Connection", "distance_km": round(distance_km, 6), "original_row": original_row},
                })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"country_code": country_code, "country_label": country_label},
    }


def main():
    OUTPUT_LEAFLET_DIR.mkdir(exist_ok=True)

    stems = set()
    for d in (OUTPUT_MATCH_RESULTS_DIR, OUTPUT_MATCH_NAME_DIR):
        if d.exists():
            for p in d.glob("*.xlsx"):
                if is_excel_lock_file(p):
                    continue
                stem = p.stem.replace("_result", "").replace("_name", "")
                if stem.startswith("cn"):
                    stems.add(stem)

    result_files = []
    for stem in sorted(stems):
        p = OUTPUT_MATCH_RESULTS_DIR / f"{stem}_result.xlsx"
        if p.exists():
            result_files.append((p, stem))
        else:
            p = OUTPUT_MATCH_NAME_DIR / f"{stem}_name.xlsx"
            if p.exists():
                result_files.append((p, stem))

    for path, stem in result_files:
        parts = stem.split("_")
        country_code = parts[1] if len(parts) >= 2 else stem
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as e:
            print(f" skip {path.name}: {e}")
            continue
        judge_col = "judge" if "judge" in df.columns else "name_judge"
        if judge_col not in df.columns:
            print(f" skip {path.name}: no judge column")
            continue
        geojson = build_geojson_for_country(df, country_code, stem)
        out_path = OUTPUT_LEAFLET_DIR / f"{stem}.geojson"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f" wrote {out_path} ({len(geojson['features'])} features)")

    print(f"GeoJSON output: {OUTPUT_LEAFLET_DIR}")


if __name__ == "__main__":
    main()
