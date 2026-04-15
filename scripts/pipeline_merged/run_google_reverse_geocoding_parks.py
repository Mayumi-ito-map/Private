"""
run_google_reverse_geocoding_parks.py

0match/国立公園.xlsx の work_lat / work_lon を使って、
以下を同時に取得する。

1. Google Geocoding API reverse geocoding
2. GeoNames nearby search

使い方:
    export GOOGLE_MAPS_API_KEY="YOUR_API_KEY"
    export GEONAMES_USERNAME="YOUR_GEONAMES_USERNAME"
    python scripts/pipeline_merged/run_google_reverse_geocoding_parks.py

出力:
    0match/国立公園_google_reverse_geocoding.xlsx
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "0match" / "国立公園.xlsx"
DEFAULT_OUTPUT = PROJECT_ROOT / "0match" / "国立公園_google_reverse_geocoding.xlsx"
DEFAULT_GOOGLE_RAW_DIR = PROJECT_ROOT / "0match" / "google_reverse_geocoding_raw"
DEFAULT_GEONAMES_RAW_DIR = PROJECT_ROOT / "0match" / "geonames_nearby_raw"

API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GEONAMES_API_URL = "https://api.geonames.org/findNearbyJSON"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="work_lat/work_lon を使って Google reverse geocoding を実行する"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="入力 Excel")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="出力 Excel")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        help="Google Maps API key。未指定時は GOOGLE_MAPS_API_KEY を使う",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Google Geocoding API の language パラメータ",
    )
    parser.add_argument(
        "--sleep-sec",
        type=float,
        default=0.1,
        help="各リクエストの待機秒数",
    )
    parser.add_argument(
        "--google-raw-dir",
        type=Path,
        default=DEFAULT_GOOGLE_RAW_DIR,
        help="Google API レスポンス JSON の保存先",
    )
    parser.add_argument(
        "--geonames-raw-dir",
        type=Path,
        default=DEFAULT_GEONAMES_RAW_DIR,
        help="GeoNames レスポンス JSON の保存先",
    )
    parser.add_argument(
        "--geonames-username",
        default=os.environ.get("GEONAMES_USERNAME", ""),
        help="GeoNames username。未指定時は GEONAMES_USERNAME を使う",
    )
    parser.add_argument(
        "--geonames-radius-km",
        type=float,
        default=30.0,
        help="GeoNames nearby の検索半径（km）",
    )
    parser.add_argument(
        "--geonames-max-rows",
        type=int,
        default=10,
        help="GeoNames nearby の取得件数上限",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="既存の reverse geocoding 列がある行をスキップする",
    )
    return parser.parse_args()


def _clean_coord(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _request_reverse_geocode(lat: str, lon: str, api_key: str, language: str) -> dict:
    params = {
        "latlng": f"{lat},{lon}",
        "language": language,
        "key": api_key,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_geonames_nearby(
    lat: str,
    lon: str,
    username: str,
    radius_km: float,
    max_rows: int,
) -> dict:
    params = {
        "lat": lat,
        "lng": lon,
        "radius": radius_km,
        "maxRows": max_rows,
        "style": "FULL",
        "username": username,
    }
    url = f"{GEONAMES_API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_result(payload: dict) -> dict:
    status = payload.get("status", "")
    results = payload.get("results", []) or []
    plus_code = payload.get("plus_code", {}) or {}

    if not results:
        return {
            "rg_status": status,
            "rg_result_count": 0,
            "rg_formatted_address": "",
            "rg_place_id": "",
            "rg_types": "",
            "rg_location_type": "",
            "rg_result_lat": "",
            "rg_result_lon": "",
            "rg_plus_code_global": plus_code.get("global_code", ""),
            "rg_plus_code_compound": plus_code.get("compound_code", ""),
            "rg_address_components": "",
        }

    top = results[0]
    geom = top.get("geometry", {}) or {}
    loc = geom.get("location", {}) or {}
    comps = top.get("address_components", []) or []

    return {
        "rg_status": status,
        "rg_result_count": len(results),
        "rg_formatted_address": top.get("formatted_address", ""),
        "rg_place_id": top.get("place_id", ""),
        "rg_types": " | ".join(top.get("types", []) or []),
        "rg_location_type": geom.get("location_type", ""),
        "rg_result_lat": loc.get("lat", ""),
        "rg_result_lon": loc.get("lng", ""),
        "rg_plus_code_global": plus_code.get("global_code", ""),
        "rg_plus_code_compound": plus_code.get("compound_code", ""),
        "rg_address_components": json.dumps(comps, ensure_ascii=False),
    }


def _extract_geonames_result(payload: dict) -> dict:
    geonames = payload.get("geonames", []) or []
    status = payload.get("status", {}) or {}

    if not geonames:
        return {
            "gn_status": status.get("message", "NO_RESULTS") if status else "NO_RESULTS",
            "gn_result_count": 0,
            "gn_top_geonameId": "",
            "gn_top_name": "",
            "gn_top_countryCode": "",
            "gn_top_fcl": "",
            "gn_top_fcode": "",
            "gn_top_distance": "",
            "gn_top_lat": "",
            "gn_top_lon": "",
            "gn_top_adminName1": "",
            "gn_top_adminName2": "",
            "gn_top_score_note": "",
        }

    top = geonames[0]
    return {
        "gn_status": "OK",
        "gn_result_count": len(geonames),
        "gn_top_geonameId": top.get("geonameId", ""),
        "gn_top_name": top.get("name", ""),
        "gn_top_countryCode": top.get("countryCode", ""),
        "gn_top_fcl": top.get("fcl", ""),
        "gn_top_fcode": top.get("fcode", ""),
        "gn_top_distance": top.get("distance", ""),
        "gn_top_lat": top.get("lat", ""),
        "gn_top_lon": top.get("lng", ""),
        "gn_top_adminName1": top.get("adminName1", ""),
        "gn_top_adminName2": top.get("adminName2", ""),
        "gn_top_score_note": "top1 is nearest GeoNames feature, not guaranteed park name",
    }


def main() -> None:
    args = parse_args()

    if not args.api_key:
        raise SystemExit(
            "API key がありません。--api-key か GOOGLE_MAPS_API_KEY を指定してください。"
        )

    print(f"input : {args.input}")
    print(f"output: {args.output}")
    print(f"google raw  : {args.google_raw_dir}")
    print(f"geonames raw: {args.geonames_raw_dir}")

    df = pd.read_excel(args.input, engine="openpyxl")
    required = ["index_ID", "work_lat", "work_lon"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"必須列がありません: {missing}")

    result_cols = [
        "rg_status",
        "rg_result_count",
        "rg_formatted_address",
        "rg_place_id",
        "rg_types",
        "rg_location_type",
        "rg_result_lat",
        "rg_result_lon",
        "rg_plus_code_global",
        "rg_plus_code_compound",
        "rg_address_components",
        "gn_status",
        "gn_result_count",
        "gn_top_geonameId",
        "gn_top_name",
        "gn_top_countryCode",
        "gn_top_fcl",
        "gn_top_fcode",
        "gn_top_distance",
        "gn_top_lat",
        "gn_top_lon",
        "gn_top_adminName1",
        "gn_top_adminName2",
        "gn_top_score_note",
    ]
    for col in result_cols:
        if col not in df.columns:
            df[col] = ""

    args.google_raw_dir.mkdir(parents=True, exist_ok=True)
    args.geonames_raw_dir.mkdir(parents=True, exist_ok=True)

    total = len(df)
    google_request_count = 0
    geonames_request_count = 0
    skip_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        index_id = str(row.get("index_ID", "")).strip()
        lat = _clean_coord(row.get("work_lat"))
        lon = _clean_coord(row.get("work_lon"))

        if not lat or not lon:
            df.at[idx, "rg_status"] = "SKIP_NO_WORK_COORD"
            skip_count += 1
            continue

        if args.skip_existing and str(row.get("rg_status", "")).strip():
            skip_count += 1
            continue

        try:
            google_payload = _request_reverse_geocode(lat, lon, args.api_key, args.language)
            extracted = _extract_result(google_payload)
            for col, value in extracted.items():
                df.at[idx, col] = value

            google_raw_path = args.google_raw_dir / f"{index_id or idx}.json"
            google_raw_path.write_text(
                json.dumps(google_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            google_request_count += 1

            if args.geonames_username:
                geonames_payload = _request_geonames_nearby(
                    lat,
                    lon,
                    args.geonames_username,
                    args.geonames_radius_km,
                    args.geonames_max_rows,
                )
                gn_extracted = _extract_geonames_result(geonames_payload)
                for col, value in gn_extracted.items():
                    df.at[idx, col] = value

                geonames_raw_path = args.geonames_raw_dir / f"{index_id or idx}.json"
                geonames_raw_path.write_text(
                    json.dumps(geonames_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                geonames_request_count += 1
            else:
                df.at[idx, "gn_status"] = "SKIP_NO_GEONAMES_USERNAME"
        except Exception as exc:  # noqa: BLE001
            df.at[idx, "rg_status"] = f"ERROR: {exc}"
            if not str(df.at[idx, "gn_status"]).strip():
                df.at[idx, "gn_status"] = f"ERROR: {exc}"
            error_count += 1

        if (idx + 1) % 50 == 0 or idx == total - 1:
            print(
                f"processed {idx + 1:,}/{total:,} "
                f"(google={google_request_count:,}, geonames={geonames_request_count:,}, "
                f"skip={skip_count:,}, error={error_count:,})",
                flush=True,
            )

        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["rg_status"] == "OK"].to_excel(writer, sheet_name="ok", index=False)
        df[df["rg_status"] != "OK"].to_excel(writer, sheet_name="not_ok", index=False)
        if "gn_status" in df.columns:
            df[df["gn_status"] == "OK"].to_excel(writer, sheet_name="geonames_ok", index=False)

    print("done.")
    print(f"google requests  : {google_request_count:,}")
    print(f"geonames requests: {geonames_request_count:,}")
    print(f"skips            : {skip_count:,}")
    print(f"errors           : {error_count:,}")


if __name__ == "__main__":
    main()
