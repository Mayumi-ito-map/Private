"""
geojson_to_excel.py

output_leaflet 内の *.geojson ファイルを Excel（*.xlsx）に変換する。

入力: output_leaflet/*.geojson
出力: output_leaflet/*.xlsx（同一フォルダ、拡張子のみ変更）

各 Feature を 1 行として出力。geometry の coordinates は lon, lat 列に展開。
properties のキーはそのまま列名として使用。
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils import is_excel_lock_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "output_leaflet"
OUTPUT_DIR = BASE_DIR / "output_leaflet"


def geojson_to_rows(geojson: dict) -> list[dict]:
    """FeatureCollection から行のリストを生成。各 Feature が 1 行。"""
    features = geojson.get("features", [])
    rows = []
    for f in features:
        props = f.get("properties") or {}
        row = dict(props)
        geom = f.get("geometry")
        if geom and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                row["lon"] = coords[0]
                row["lat"] = coords[1]
        rows.append(row)
    return rows


def convert_one(path: Path) -> tuple[Path, int] | None:
    """1つの GeoJSON を Excel に変換。(出力パス, 行数) を返す。"""
    with open(path, encoding="utf-8") as f:
        geojson = json.load(f)
    rows = geojson_to_rows(geojson)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    out_path = path.with_suffix(".xlsx")
    df.to_excel(out_path, index=False, engine="openpyxl")
    return out_path, len(rows)


def main():
    geojson_files = sorted(INPUT_DIR.glob("cn*_*.geojson"))
    geojson_files = [p for p in geojson_files if not is_excel_lock_file(p)]
    for path in geojson_files:
        try:
            result = convert_one(path)
            if result:
                out, n = result
                print(f"  {path.name} → {out.name} ({n} rows)")
        except Exception as e:
            print(f"  skip {path.name}: {e}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
