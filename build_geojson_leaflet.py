"""
build_geojson_leaflet.py

output_match_results_quote_variants の Excel から、国毎に GeoJSON を生成する。
Leaflet で 5 種類を色分け表示する用。

入力: output_match_results_quote_variants/*.xlsx（*_result_result.xlsx 等）
出力: output_leaflet/{country}.geojson（ファイル名は「_result」を除く）

色分け:
  local         : #ff0000
  geonames_hits : #0000ff
  Stage1_hit    : #ffc800
  Stage2_hit    : #00ff00
  Stage3_hit    : #de47d9

仕様: memo/geojson-Leaflet作成の指示.md
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pandas as pd

from utils import is_excel_lock_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "output_match_results_quote_variants"
OUTPUT_DIR = BASE_DIR / "output_leaflet"

# 5種類の marker-color（指示通り）
COLOR_LOCAL = "#ff0000"
COLOR_GEONAMES_HITS = "#0000ff"
COLOR_STAGE1 = "#ffc800"
COLOR_STAGE2 = "#00ff00"
COLOR_STAGE3 = "#de47d9"

# Excel列名 → GeoJSON properties 表示名（local）
COL_LOCUMN_TO_DISPLAY = {
    "index_ID": "local_ID",
    "修正後和文地名": "Japanese",
    "修正後欧文地名": "English",
    "num": "local_cat",
    "local_lat": "local_lat",
    "local_lon": "local_lon",
}


def parse_hits(value) -> list[dict]:
    """Excel のセル（geonames_hits / Stage1_hit / Stage2_hit / Stage3_hit）を list[dict] に復元。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
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
                return [x for x in parsed if isinstance(x, dict)]
            return [parsed] if isinstance(parsed, dict) else []
        except (ValueError, SyntaxError):
            return []
    return []


def safe_float(x, default=None):
    try:
        v = float(x)
        if math.isnan(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def geoname_record_to_properties(r: dict) -> dict:
    """pkl/Excel 由来の1件を、指示の GeoNames 項目に揃える。"""
    lat = safe_float(r.get("lat") or r.get("latitude"))
    lon = safe_float(r.get("lon") or r.get("longitude"))
    alt = r.get("alternatenames")
    if isinstance(alt, list):
        alternatenames = ",".join(str(a) for a in alt) if alt else ""
    else:
        alternatenames = str(alt) if alt else ""
    return {
        "geonameid": r.get("geonameid") or r.get("id"),
        "name": r.get("name", ""),
        "asciiname": r.get("asciiname", ""),
        "alternatenames": alternatenames,
        "latitude": lat,
        "longitude": lon,
        "feature_class": r.get("feature_class") or r.get("fcl", ""),
        "feature_code": r.get("feature_code") or r.get("fcode", ""),
        "country_code": r.get("country_code") or r.get("ccode") or r.get("cc", ""),
    }


def add_local_feature(features: list, row: pd.Series, row_index_1based: int) -> None:
    """1行分の local ポイントを1件追加。"""
    local_lat = safe_float(row.get("local_lat"))
    local_lon = safe_float(row.get("local_lon"))
    if local_lat is None or local_lon is None:
        return
    props = {"marker-color": COLOR_LOCAL, "type": "Local", "original_row": row_index_1based}
    for col, display in COL_LOCUMN_TO_DISPLAY.items():
        if col in row.index:
            v = row[col]
            if pd.notna(v):
                props[display] = v
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [local_lon, local_lat]},
        "properties": props,
    })


def add_geoname_features(
    features: list,
    hits: list[dict],
    hit_type: str,
    color: str,
    row_index_1based: int,
) -> None:
    """GeoNames ヒットを複数 Point として追加。"""
    for r in hits:
        lat = safe_float(r.get("lat") or r.get("latitude"))
        lon = safe_float(r.get("lon") or r.get("longitude"))
        if lat is None or lon is None:
            continue
        p = geoname_record_to_properties(r)
        p["marker-color"] = color
        p["type"] = "GeoNames"
        p["hit_type"] = hit_type
        p["original_row"] = row_index_1based
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": p,
        })


def excel_stem_to_geojson_stem(stem: str) -> str:
    """_result_result / _result を除いた国ラベルにする。"""
    s = stem
    while s.endswith("_result"):
        s = s[:-7]
    return s


def build_geojson(df: pd.DataFrame, country_label: str) -> dict:
    """DataFrame から GeoJSON FeatureCollection を組み立てる。"""
    features = []
    for idx, row in df.iterrows():
        row_index_1based = int(idx) + 1

        add_local_feature(features, row, row_index_1based)

        gh = parse_hits(row.get("geonames_hits"))
        add_geoname_features(features, gh, "geonames_hits", COLOR_GEONAMES_HITS, row_index_1based)

        for col, color in (
            ("Stage1_hit", COLOR_STAGE1),
            ("Stage2_hit", COLOR_STAGE2),
            ("Stage3_hit", COLOR_STAGE3),
        ):
            hits = parse_hits(row.get(col))
            add_geoname_features(features, hits, col, color, row_index_1based)

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"country_label": country_label},
    }


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    excel_files = sorted(INPUT_DIR.glob("cn*_*.xlsx"))
    excel_files = [p for p in excel_files if not is_excel_lock_file(p)]

    if not excel_files:
        print(f"No Excel files in {INPUT_DIR}")
        return

    for path in excel_files:
        stem = path.stem
        country_label = excel_stem_to_geojson_stem(stem)
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as e:
            print(f" skip {path.name}: {e}")
            continue

        geojson = build_geojson(df, country_label)
        out_path = OUTPUT_DIR / f"{country_label}.geojson"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f" wrote {out_path} ({len(geojson['features'])} features)")

    print(f"GeoJSON output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
