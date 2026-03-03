"""
geonames_loader.py

geonames_master.pkl を読み、国コード（海外領土対応）でフィルタした
地名辞書と GeoDataFrame を提供する共通モジュール。
司令塔①・司令塔②の両方で利用する。
"""
from __future__ import annotations

import pickle
import unicodedata
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


# 国コードのエイリアス（Excel の表記ゆれ → GeoNames の正式コード）
# 例: KO/KOR は KR、PRK は KP
COUNTRY_CODE_ALIASES = {
    "KO": "KR",
    "KOR": "KR",
    "PRK": "KP",
}


def resolve_country_codes(
    excel_country_code: str,
    overseas_map: dict,
) -> list[str]:
    """
    Excel側の2桁国コードから、マッチング対象のGeoNames国コードリストを返す。
    海外領土がある場合は複数コードになる。
    エイリアス（KO→KR 等）で補正する。
    """
    resolved = COUNTRY_CODE_ALIASES.get(excel_country_code, excel_country_code)
    codes = overseas_map.get(resolved, [resolved])
    if resolved not in codes:
        codes = [resolved] + [c for c in codes if c != resolved]
    return list(dict.fromkeys(codes))


def get_records_by_country_codes(
    db: dict,
    country_codes: list[str],
) -> list[dict]:
    """
    by_ccode と by_id から、指定国コード群に属する全レコードのリストを返す。
    各レコードは geonameid, name, asciiname, alternatenames, lat, lon 等を保持。
    ※ build_geonames_db は "by_cc" で保存するため、by_ccode が無い場合は by_cc を使用。
    """
    by_id = db["by_id"]
    by_ccode = db.get("by_ccode") or db.get("by_cc", {})
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


def build_placename_dict(records: list[dict], field: str = "name") -> dict:
    """
    レコードリストから、完全一致用の辞書を構築する。
    asciiname は使用しない（name / alternatenames で重み付けマッチングを想定）。

    Args:
        records: GeoNames レコードのリスト
        field: "name" または "alternatenames"。どちらのフィールドのみを辞書に含めるか。

    Returns:
        名前 -> [record, ...] の辞書（geonameid で重複は別レコードのまま）
    """
    expanded = {}
    for record in records:
        names = []
        if field == "name":
            if record.get("name"):
                names.append(record["name"])
        elif field == "alternatenames":
            alt = record.get("alternatenames")
            if isinstance(alt, list):
                names.extend(alt)
            elif isinstance(alt, str) and alt:
                names.extend([a.strip() for a in alt.split(",") if a.strip()])
        for n in names:
            if n:
                # ハングル・漢字の Unicode 正規化（NFC）で表記ゆれを吸収
                key = unicodedata.normalize("NFC", n)
                expanded.setdefault(key, []).append(record)
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
    field: str = "name",
):
    """
    既にメモリに読み込んだ db から、国コードでフィルタした結果を返す。
    司令塔で pkl を1回だけ読み、国ループ内ではこの関数を使うと高速。

    Args:
        field: "name" または "alternatenames"。placename_dict の構築に使用するフィールド。

    Returns:
        tuple: (placename_dict, records, gdf)
        - placename_dict: 名前 -> [record, ...]
        - records: 国コード群に属する全レコードリスト
        - gdf: 同上の GeoDataFrame（距離・地図用）
    """
    resolved = resolve_country_codes(excel_country_code, overseas_map)
    records = get_records_by_country_codes(db, resolved)
    placename_dict = build_placename_dict(records, field=field)
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
