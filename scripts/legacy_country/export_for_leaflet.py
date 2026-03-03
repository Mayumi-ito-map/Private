"""
export_for_leaflet.py

司令塔①②の結果を、Leaflet 地図用の GeoJSON に変換する。
- ローカル地名（local_lat, local_lon があれば Point）
- GeoNames 候補（Point、fcl/fcode で属性色分け可能）
- ローカル‐候補間の Connection（LineString + distance_km）

入力: output_match/*.xlsx および output_match_results/*.xlsx（あれば優先）
出力: output_leaflet/{country_label}.geojson
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pandas as pd

from utils import is_excel_lock_file

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project/
OUTPUT_MATCH_DIR = BASE_DIR / "output_match"
OUTPUT_MATCH_RESULTS_DIR = BASE_DIR / "output_match_results"
OUTPUT_LEAFLET_DIR = BASE_DIR / "output_leaflet"

# Leaflet見本に合わせた色・属性
COLOR_LOCAL = "#0000ff"
COLOR_GEONAMES = "#ff0000"


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """2点間の距離（km）を概算。"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_candidates(value) -> list[dict]:
    """Excel から読み込んだ候補（geonames_hits または Stage*_hit）を list[dict] に復元。"""
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


def row_candidates(row: pd.Series) -> list[dict]:
    """1行から GeoNames 候補リストを取得。judge に応じて geonames_hits または Stage*_hit を使用。"""
    judge = str(row.get("judge", "")).strip()
    if judge != "0":
        return parse_candidates(row.get("geonames_hits"))
    for col in ("Stage1_hit", "Stage2_hit", "Stage3_hit"):
        hits = parse_candidates(row.get(col))
        if hits:
            return hits
    return []


def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def build_geojson_for_country(df: pd.DataFrame, country_code: str, country_label: str) -> dict:
    """
    DataFrame（司令塔①または②の結果）から GeoJSON FeatureCollection を組み立てる。
    - Local Point（local_lat, local_lon がある行）
    - GeoNames Point（各候補）
    - Connection LineString（Local と各候補を結び、distance_km を付与）
    """
    features = []
    for idx, row in df.iterrows():
        original_row = int(idx) + 1  # 1-based（Excel行イメージ）
        local_lat = safe_float(row.get("local_lat"))
        local_lon = safe_float(row.get("local_lon"))
        name_local = str(row.get("修正後欧文地名", row.get("normalized_candidates", "")))[:200]
        candidates = row_candidates(row)

        # Local Point
        if local_lat is not None and local_lon is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [local_lon, local_lat]},
                "properties": {
                    "type": "Local",
                    "name": name_local,
                    "original_row": original_row,
                    "marker-color": COLOR_LOCAL,
                },
            })

        # GeoNames Points + Connection
        for c in candidates:
            gid = c.get("geonameid") or c.get("id")
            lat = safe_float(c.get("lat"))
            lon = safe_float(c.get("lon"))
            if lat is None or lon is None:
                continue
            name_gn = str(c.get("name", ""))[:200]
            fcode = c.get("fcode", "")
            fcl = c.get("fcl", "")

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "type": "GeoNames",
                    "id": str(gid),
                    "country": country_code,
                    "original_row": original_row,
                    "marker-color": COLOR_GEONAMES,
                    "name": name_gn,
                    "fcode": fcode,
                    "fcl": fcl,
                },
            })

            if local_lat is not None and local_lon is not None:
                distance_km = haversine_km(local_lon, local_lat, lon, lat)
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[local_lon, local_lat], [lon, lat]],
                    },
                    "properties": {
                        "type": "Connection",
                        "distance_km": round(distance_km, 6),
                        "original_row": original_row,
                    },
                })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "country_code": country_code,
            "country_label": country_label,
        },
    }


def main():
    OUTPUT_LEAFLET_DIR.mkdir(exist_ok=True)

    # 国ごと: 司令塔②結果を優先、なければ司令塔①結果を使用
    stems = set()
    for d in (OUTPUT_MATCH_RESULTS_DIR, OUTPUT_MATCH_DIR):
        if d.exists():
            for p in d.glob("cn*_*.xlsx"):
                if not is_excel_lock_file(p):
                    stems.add(p.stem)
    result_files = []
    for stem in sorted(stems):
        p = OUTPUT_MATCH_RESULTS_DIR / f"{stem}.xlsx"
        if p.exists():
            result_files.append(p)
        else:
            p = OUTPUT_MATCH_DIR / f"{stem}.xlsx"
            if p.exists():
                result_files.append(p)

    for path in result_files:
        stem = path.stem
        parts = stem.split("_")
        country_code = parts[1] if len(parts) >= 2 else stem

        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as e:
            print(f" skip {path.name}: {e}")
            continue

        if "judge" not in df.columns:
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
