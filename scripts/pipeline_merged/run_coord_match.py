"""
座標近傍マッチ（司令塔① 補助）: Excel の緯度経度から GeoNames を近傍探索

責務:
- 合体 Excel（excel_local_merged/*.xlsx）の座標列（既定: go_lat, go_lon）を読む
- 入力ファイルの指定は run_local_build.py と同じ: EXCEL_DIR と MERGED_PATTERNS を編集する（--input は不要）
- 国コード cc ごとに geonames_master.pkl のレコードを対象に、距離（Haversine）で候補を選ぶ
- lo_fcl ごとの FCL フィルタ・距離閾値は run_local_build.py と同じ定数を参照可能（下で複製設定）

閾値が None の lo_fcl: フィルタ後レコードのうち「最も近い 1 件のみ」を採用（1 件でも距離は出力）。
閾値が数値: 閾値以内の全レコードを候補とし、0 / 1 / 2+ 件で judge。

※ 地名完全一致は行わない。司令塔①とは別パイプラインとして使う。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from geonames_loader import (  # noqa: E402
    get_records_by_country_codes,
    load_master_pkl,
    resolve_country_codes,
)

# =========================================================
# パス・入出力
# =========================================================

BASE_DIR = PROJECT_ROOT
EXCEL_DIR = BASE_DIR / "excel_local_merged"
OVERSEAS_JSON = BASE_DIR / "config" / "overseas_territories.json"
OUTPUT_DIR = BASE_DIR / "output_match_coord"

# 合体ファイルのパターン（run_local_build.py と同様。テスト時は 1 件のみにすると高速）
MERGED_PATTERNS = [
    # "cn000_asia.xlsx",
    # "cn100_europe.xlsx",
    # "cn200_africa.xlsx",
    # "国立公園.xlsx",
    # "cn300_america.xlsx",
    # "cn450_oceania.xlsx",
    # "cn026_KR-KP_asia.xlsx",
    # "cn028_CN_asia.xlsx",
    "cn001_JP_日本_go.xlsx",
    # "cn001_JP_日本.xlsx",
]

EXCLUDE_COL = "exclude"
CC_COL = "cc"

# 座標列（Google 役所座標など）
COORD_LAT_COL = "go_lat"
COORD_LON_COL = "go_lon"

# run_local_build と揃えた FCL 制限（enabled=True のときのみ GeoNames fcl で絞る）
FCL_FILTERS = {
    "P": {"enabled": False, "gn_allowed": ("P",)},
    "A": {"enabled": False, "gn_allowed": ("A", "L")},
    "S": {"enabled": False, "gn_allowed": ("S", "V")},
    "T": {"enabled": False, "gn_allowed": ("H", "T")},
}

# km。None は「最寄り 1 件のみ」モード（上限距離は max_km_nearest で別指定可）
DISTANCE_THRESHOLDS = {
    "P": 30,
    "A": 500,
    "S": 10,
    "T": None,
}

# 最寄り 1 件モード時、これを指定するとこの km を超えたら hit-0。None なら上限なし
MAX_KM_NEAREST_DEFAULT: float | None = None

EARTH_RADIUS_KM = 6371.0

# 出力列ブロック（local_lon の後に置く想定で run_local_build の並びに近づける）
COORD_MERGE_ORDER = [
    "coord_edited_ref",
    "coord_hit_len",
    "coord_judge",
    "coord_distance_km",
    "coord_matched_geonameid",
    "coord_matched_name",
    "coord_matched_fcl",
    "coord_matched_fcode",
    "coord_matched_lat",
    "coord_matched_lon",
]


def load_overseas_territories() -> dict:
    if not OVERSEAS_JSON.exists():
        return {}
    with open(OVERSEAS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _filter_records_by_lo_fcl(
    records: list[dict],
    lo_fcl: str | None,
) -> list[dict]:
    """lo_fcl に応じて GeoNames レコードを fcl で絞る。未指定・空は絞らない。"""
    if lo_fcl is None:
        return records
    lf = str(lo_fcl).strip()
    if not lf:
        return records
    cfg = FCL_FILTERS.get(lf)
    if not cfg or not cfg.get("enabled"):
        return records
    allowed = tuple(cfg.get("gn_allowed", ()))
    if not allowed:
        return records
    return [r for r in records if r.get("fcl", "") in allowed]


def _records_to_lat_lon_arrays(records: list[dict]) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """lat/lon 欠損でないレコードだけ残し、配列と対応リストを返す。"""
    kept: list[dict] = []
    lats: list[float] = []
    lons: list[float] = []
    for r in records:
        try:
            la = float(r.get("lat"))
            lo = float(r.get("lon"))
        except (TypeError, ValueError):
            continue
        if math.isnan(la) or math.isnan(lo):
            continue
        kept.append(r)
        lats.append(la)
        lons.append(lo)
    if not kept:
        return np.array([]), np.array([]), []
    return np.asarray(lats, dtype=float), np.asarray(lons, dtype=float), kept


def _haversine_km_vec(lat0: float, lon0: float, lat_arr: np.ndarray, lon_arr: np.ndarray) -> np.ndarray:
    """スカラー点から各 (lat_arr, lon_arr) までの大圏距離（km）。"""
    if lat_arr.size == 0:
        return np.array([])
    lat0_r = math.radians(lat0)
    lon0_r = math.radians(lon0)
    lat_r = np.radians(lat_arr)
    lon_r = np.radians(lon_arr)
    dlat = lat_r - lat0_r
    dlon = lon_r - lon0_r
    a = np.sin(dlat / 2.0) ** 2 + math.cos(lat0_r) * np.cos(lat_r) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def _pick_hits_nearest(
    dists: np.ndarray,
    kept: list[dict],
    max_km: float | None,
) -> list[tuple[dict, float]]:
    """最寄り 1 件。max_km があってそれを超えたら空リスト。"""
    if dists.size == 0:
        return []
    i = int(np.argmin(dists))
    d = float(dists[i])
    if max_km is not None and d > max_km:
        return []
    return [(kept[i], d)]


def _pick_hits_threshold(
    dists: np.ndarray,
    kept: list[dict],
    threshold_km: float,
) -> list[tuple[dict, float]]:
    """閾値以内の全件（距離昇順）。"""
    if dists.size == 0:
        return []
    idx = np.where(dists <= threshold_km)[0]
    if idx.size == 0:
        return []
    order = idx[np.argsort(dists[idx])]
    return [(kept[int(j)], float(dists[int(j)])) for j in order]


def _format_pipe_floats(vals: list[float]) -> str:
    return " | ".join(f"{v:.2f}" for v in vals)


def _format_pipe_strs(vals: list[str]) -> str:
    return " | ".join(vals)


def _cache_key_for_row(lo_fcl_val) -> str:
    if pd.isna(lo_fcl_val):
        return "__default__"
    s = str(lo_fcl_val).strip()
    return s if s else "__default__"


def match_coords_one_row(
    lat: float,
    lon: float,
    lo_fcl_val,
    la_arr: np.ndarray,
    lo_arr: np.ndarray,
    kept: list[dict],
    max_km_nearest: float | None,
) -> dict:
    dists = _haversine_km_vec(lat, lon, la_arr, lo_arr)

    lf = str(lo_fcl_val).strip() if pd.notna(lo_fcl_val) and str(lo_fcl_val).strip() else ""
    th = DISTANCE_THRESHOLDS.get(lf) if lf in DISTANCE_THRESHOLDS else None
    if lf in DISTANCE_THRESHOLDS and th is None:
        hits = _pick_hits_nearest(dists, kept, max_km_nearest)
    elif lf in DISTANCE_THRESHOLDS and isinstance(th, (int, float)):
        hits = _pick_hits_threshold(dists, kept, float(th))
    else:
        # lo_fcl 未設定または辞書に無い → 全レコード（未 fcl 絞り）で最寄り
        hits = _pick_hits_nearest(dists, kept, max_km_nearest)

    if not hits:
        return {
            "coord_hit_len": 0,
            "coord_judge": "0",
            "coord_distance_km": "",
            "coord_matched_geonameid": "",
            "coord_matched_name": "",
            "coord_matched_fcl": "",
            "coord_matched_fcode": "",
            "coord_matched_lat": "",
            "coord_matched_lon": "",
        }

    recs = [h[0] for h in hits]
    ds = [h[1] for h in hits]
    n = len(recs)
    judge = "1" if n == 1 else "2+"

    def _g(k):
        return [("" if r.get(k) is None else str(r.get(k))) for r in recs]

    return {
        "coord_hit_len": n,
        "coord_judge": judge,
        "coord_distance_km": _format_pipe_floats(ds),
        "coord_matched_geonameid": _format_pipe_strs(_g("geonameid")),
        "coord_matched_name": _format_pipe_strs(_g("name")),
        "coord_matched_fcl": _format_pipe_strs(_g("fcl")),
        "coord_matched_fcode": _format_pipe_strs(_g("fcode")),
        "coord_matched_lat": _format_pipe_strs(_g("lat")),
        "coord_matched_lon": _format_pipe_strs(_g("lon")),
    }


def _reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    ordered: list[str] = []
    for c in cols:
        if c not in COORD_MERGE_ORDER and c not in ("coord_lat", "coord_lon"):
            ordered.append(c)
    for c in ("coord_lat", "coord_lon"):
        if c in cols:
            ordered.append(c)
    for c in COORD_MERGE_ORDER:
        if c in cols:
            ordered.append(c)
    for c in cols:
        if c not in ordered:
            ordered.append(c)
    return df[[c for c in ordered]]


def _empty_coord_result() -> dict:
    return {
        "coord_hit_len": 0,
        "coord_judge": "0",
        "coord_distance_km": "",
        "coord_matched_geonameid": "",
        "coord_matched_name": "",
        "coord_matched_fcl": "",
        "coord_matched_fcode": "",
        "coord_matched_lat": "",
        "coord_matched_lon": "",
    }


def _get_lf_arrays(
    country_bucket: dict,
    lf_key: str,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """国ごとの状態に、lo_fcl キー別の lat/lon 配列をキャッシュ。"""
    by_lf: dict = country_bucket.setdefault("by_lf", {})
    if lf_key not in by_lf:
        lf = None if lf_key == "__default__" else lf_key
        filtered = _filter_records_by_lo_fcl(country_bucket["records"], lf)
        by_lf[lf_key] = _records_to_lat_lon_arrays(filtered)
    return by_lf[lf_key]


def process_dataframe(
    df: pd.DataFrame,
    db: dict,
    overseas_map: dict,
    lat_col: str,
    lon_col: str,
    max_km_nearest: float | None,
) -> pd.DataFrame:
    if CC_COL not in df.columns:
        raise ValueError(f"{CC_COL} 列がありません")
    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"座標列 {lat_col}, {lon_col} のいずれかがありません")

    df = df.copy()
    if "fcl" in df.columns and "lo_fcl" not in df.columns:
        df = df.rename(columns={"fcl": "lo_fcl"})

    df["coord_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    df["coord_lon"] = pd.to_numeric(df[lon_col], errors="coerce")

    # 参照用（どの列から読んだか）
    df["coord_edited_ref"] = f"{lat_col},{lon_col}"

    cc_state: dict[str, dict] = {}
    out_rows: list[dict] = []

    for idx, row in df.iterrows():
        cc = str(row[CC_COL]).strip() if pd.notna(row[CC_COL]) else ""
        if not cc:
            out_rows.append(_empty_coord_result())
            continue

        if cc not in cc_state:
            codes = resolve_country_codes(cc, overseas_map)
            cc_state[cc] = {
                "records": get_records_by_country_codes(db, codes),
            }

        lf_key = _cache_key_for_row(row["lo_fcl"]) if "lo_fcl" in row.index else "__default__"
        la_arr, lo_arr, kept = _get_lf_arrays(cc_state[cc], lf_key)

        lat, lon = row["coord_lat"], row["coord_lon"]
        if pd.isna(lat) or pd.isna(lon):
            out_rows.append(_empty_coord_result())
            continue

        lo_fcl_val = row["lo_fcl"] if "lo_fcl" in row.index else np.nan
        r = match_coords_one_row(
            float(lat), float(lon), lo_fcl_val, la_arr, lo_arr, kept, max_km_nearest
        )
        out_rows.append(r)

    meta = pd.DataFrame(out_rows, index=df.index)
    df_out = pd.concat([df, meta], axis=1)
    return _reorder_columns(df_out)


def _is_excluded(val) -> bool:
    if pd.isna(val):
        return False
    s = str(val).strip()
    return s == "1" or s == "1.0"


def run_file(
    merged_path: Path,
    db: dict,
    overseas_map: dict,
    lat_col: str,
    lon_col: str,
    max_km_nearest: float | None,
    out_dir: Path,
) -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df_all = pd.read_excel(merged_path)

    if EXCLUDE_COL in df_all.columns:
        mask = df_all[EXCLUDE_COL].apply(_is_excluded)
        n_ex = int(mask.sum())
        if n_ex:
            df_all = df_all[~mask].copy()
            print(f"  exclude 除外: {n_ex} 行")

    df_out = process_dataframe(df_all, db, overseas_map, lat_col, lon_col, max_km_nearest)

    out_dir.mkdir(parents=True, exist_ok=True)
    base = merged_path.stem
    out_path = out_dir / f"{base}_coord_match.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name="all", index=False)
        if "coord_judge" in df_out.columns:
            for j, sheet in (("0", "judge_0"), ("1", "judge_1"), ("2+", "judge_2plus")):
                sub = df_out[df_out["coord_judge"] == j]
                sub.to_excel(writer, sheet_name=sheet, index=False)
    print(f"  -> {out_path}")

    jcol = df_out["coord_judge"]
    print(
        f"  coord_judge: 0={int((jcol == '0').sum())}, "
        f"1={int((jcol == '1').sum())}, 2+={int((jcol == '2+').sum())}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="座標近傍で GeoNames にマッチ（入力は MERGED_PATTERNS + EXCEL_DIR、司令塔①と同様）"
    )
    parser.add_argument("--lat-col", default=COORD_LAT_COL, help="緯度列名")
    parser.add_argument("--lon-col", default=COORD_LON_COL, help="経度列名")
    parser.add_argument(
        "--max-km-nearest",
        type=float,
        default=None,
        help="最寄り 1 件モード時の上限距離（km）。未指定は定数 MAX_KM_NEAREST_DEFAULT",
    )
    args = parser.parse_args()

    merged_files = [EXCEL_DIR / p for p in MERGED_PATTERNS if (EXCEL_DIR / p).exists()]
    if not merged_files:
        print(f"合体Excelが見つかりません: {EXCEL_DIR}")
        print(f"  期待: {MERGED_PATTERNS}")
        return

    print(f"入力: {EXCEL_DIR}")
    print(f"対象: {[p.name for p in merged_files]}\n")

    max_km = args.max_km_nearest if args.max_km_nearest is not None else MAX_KM_NEAREST_DEFAULT

    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.\n")

    overseas_map = load_overseas_territories()
    print(f"出力: {OUTPUT_DIR}\n")

    for merged_path in merged_files:
        print(f"=== {merged_path.name} ===")
        run_file(
            merged_path,
            db,
            overseas_map,
            args.lat_col,
            args.lon_col,
            max_km,
            OUTPUT_DIR,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
