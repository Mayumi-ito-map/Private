"""
geonames_loader.py

geonames_master.pkl を読み、国コード（海外領土対応）でフィルタした
地名辞書と GeoDataFrame を提供する共通モジュール。
司令塔①・司令塔②の両方で利用する。
"""
from __future__ import annotations

import pickle
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

BASE_DIR = Path(__file__).resolve().parent
PKL_PATH = BASE_DIR / "geonames_master.pkl"


def load_master_pkl(pkl_path: Path | None = None) -> dict:
    """geonames_master.pkl を読み、by_id / by_ccode 等を返す。"""
    path = pkl_path or PKL_PATH
    if not path.exists():
        raise FileNotFoundError(f"geonames_master.pkl が見つかりません: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def resolve_country_codes(
    excel_country_code: str,
    overseas_map: dict,
) -> list[str]:
    """
    Excel側の2桁国コードから、マッチング対象のGeoNames国コードリストを返す。
    海外領土がある場合は複数コードになる。
    """
    codes = overseas_map.get(excel_country_code, [excel_country_code])
    if excel_country_code not in codes:
        codes = [excel_country_code] + [c for c in codes if c != excel_country_code]
    return list(dict.fromkeys(codes))


def get_records_by_country_codes(
    db: dict,
    country_codes: list[str],
) -> list[dict]:
    """
    by_ccode と by_id から、指定国コード群に属する全レコードのリストを返す。
    各レコードは geonameid, name, asciiname, alternatenames, lat, lon 等を保持。
    """
    by_id = db["by_id"]
    by_ccode = db.get("by_ccode", {})
    geonameids = []
    for cc in country_codes:
        geonameids.extend(by_ccode.get(cc, []))
    geonameids = list(dict.fromkeys(geonameids))
    records = []
    for gid in geonameids:
        r = by_id.get(gid)
        if r is not None:
            records.append(dict(r))
    return records


def build_placename_dict(records: list[dict]) -> dict:
    """
    レコードリストから、完全一致用の辞書を構築する。
    キー: name / asciiname / alternatenames の各文字列
    値: その名前に対応するレコードのリスト（geonameid で重複は別レコードのまま）
    """
    expanded = {}
    for record in records:
        names = []
        if record.get("name"):
            names.append(record["name"])
        if record.get("asciiname"):
            names.append(record["asciiname"])
        alt = record.get("alternatenames")
        if isinstance(alt, list):
            names.extend(alt)
        elif isinstance(alt, str) and alt:
            names.extend([a.strip() for a in alt.split(",") if a.strip()])
        for n in names:
            if n:
                expanded.setdefault(n, []).append(record)
    return expanded


def records_to_gdf(records: list[dict]) -> gpd.GeoDataFrame:
    """
    レコードのリストを GeoDataFrame に変換する。
    lat/lon から Point ジオメトリを生成。次の段階（Leaflet・距離計測）を想定。
    """
    if not records:
        return gpd.GeoDataFrame()

    rows = []
    for r in records:
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        rows.append({
            "geonameid": r.get("geonameid"),
            "name": r.get("name"),
            "asciiname": r.get("asciiname"),
            "lat": lat,
            "lon": lon,
            "fcl": r.get("fcl"),
            "fcode": r.get("fcode"),
            "ccode": r.get("ccode"),
            "geometry": Point(float(lon), float(lat)),
        })
    if not rows:
        return gpd.GeoDataFrame()
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return gdf


def get_geonames_for_country(
    db: dict,
    excel_country_code: str,
    overseas_map: dict,
):
    """
    既にメモリに読み込んだ db から、国コードでフィルタした結果を返す。
    司令塔で pkl を1回だけ読み、国ループ内ではこの関数を使うと高速。

    Returns:
        tuple: (placename_dict, records, gdf)
        - placename_dict: 名前 -> [record, ...]
        - records: 国コード群に属する全レコードリスト
        - gdf: 同上の GeoDataFrame（距離・地図用）
    """
    resolved = resolve_country_codes(excel_country_code, overseas_map)
    records = get_records_by_country_codes(db, resolved)
    placename_dict = build_placename_dict(records)
    gdf = records_to_gdf(records)
    return placename_dict, records, gdf


def load_geonames_for_matching(
    excel_country_code: str,
    overseas_map: dict,
    pkl_path: Path | None = None,
):
    """
    司令塔用の一括取得（pkl を毎回読み込む版）。
    国ループの外で pkl を1回だけ読み、get_geonames_for_country(db, ...) を使うと高速。

    Returns:
        tuple: (placename_dict, records, gdf)
    """
    db = load_master_pkl(pkl_path)
    return get_geonames_for_country(db, excel_country_code, overseas_map)
