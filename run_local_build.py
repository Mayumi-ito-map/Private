"""
司令塔① : ローカル候補生成 + GeoNames（geonames_master.pkl）完全一致

責務：
- ローカルExcelの「修正後欧文地名」を読む
- normalizers.normalize_comma_abb により 1→N 候補生成
- config/overseas_territories.json を考慮して国コードを解決
- geonames_master.pkl（by_id / by_ccode）から地名を取得し、完全一致で判定
- geonameid でユニーク化、judge(0 / 1 / 2+) を付与
- 各国 _result.xlsx を output_match に出力、world_stats.xlsx を同時生成
- 緯度経度は pkl の lat/lon を保持（次の段階の地図・距離計測を想定）

※ Stage1/2/3 は司令塔②の責務
"""

import json
import pandas as pd
import warnings
from pathlib import Path

from geonames_loader import load_master_pkl, get_geonames_for_country
from normalizers.normalize_comma_abb import normalize_comma_abb


# =========================================================
# パス設定
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
EXCEL_DIR = BASE_DIR / "excel_local"
OVERSEAS_JSON = BASE_DIR / "config" / "overseas_territories.json"
OUTPUT_DIR = BASE_DIR / "output_match"
OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_COL = "修正後欧文地名"

# ローカル緯度経度（次の段階: Leaflet・距離計測用）。Excelに無ければ欠損のまま出力。
LOCAL_LAT_LON_COLUMNS = [
    ("lat", "long"),           # 別々の列
    ("latitude", "longitude"),
    ("緯度", "経度"),
]
LOCAL_LATLONG_SINGLE_COL = "lat,long"  # 1列で "lat,lon" の形式


# =========================================================
# 海外領土ロード
# =========================================================

def load_overseas_territories():
    if not OVERSEAS_JSON.exists():
        return {}
    with open(OVERSEAS_JSON, encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# 国コード抽出（Excelファイル名から）
# =========================================================

def extract_country_code(path: Path) -> str:
    """例: cn002_AZ_アゼルバイジャン_AZE.xlsx → AZ"""
    parts = path.stem.split("_")
    if len(parts) >= 2:
        return parts[1]
    return ""


# =========================================================
# GeoNamesヒット判定（geonameid ユニーク化）
# =========================================================

def match_geonames_candidates(candidates: list, placename_dict: dict):
    """
    candidates: 正規化後の地名候補リスト
    placename_dict: 名前 -> [record, ...]（record は geonameid, lat, lon 等を含む）
    返値: (unique_hits, matched_keys)
    """
    hits = []
    matched_keys = []
    for name in candidates:
        if name in placename_dict:
            hits.extend(placename_dict[name])
            matched_keys.append(name)

    unique = {}
    for r in hits:
        geoid = r.get("geonameid")
        if geoid:
            unique[geoid] = r
    unique_hits = list(unique.values())
    return unique_hits, matched_keys


# =========================================================
# 出力Excel名
# =========================================================

def make_output_excel_name(excel_path: Path) -> Path:
    """cn002_AZ_アゼルバイジャン_AZE.xlsx → output_match/cn002_AZ_アゼルバイジャン_result.xlsx"""
    parts = excel_path.stem.split("_")
    base = "_".join(parts[:3])
    return OUTPUT_DIR / f"{base}_result.xlsx"


# =========================================================
# ローカル緯度経度の正規化（次の段階の地図・距離用）
# =========================================================

def ensure_local_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel の lat/lon を探し、列 local_lat / local_lon に統一する。
    対応: (lat, long), (latitude, longitude), (緯度, 経度), または 1列 "lat,long"。
    """
    if "local_lat" in df.columns and "local_lon" in df.columns:
        return df
    lat_col, lon_col = None, None
    for c1, c2 in LOCAL_LAT_LON_COLUMNS:
        if c1 in df.columns and c2 in df.columns:
            lat_col, lon_col = c1, c2
            break
    if lat_col and lon_col:
        df = df.copy()
        df["local_lat"] = pd.to_numeric(df[lat_col], errors="coerce")
        df["local_lon"] = pd.to_numeric(df[lon_col], errors="coerce")
        return df
    if LOCAL_LATLONG_SINGLE_COL in df.columns:
        def split_latlon(val):
            if pd.isna(val) or not isinstance(val, str):
                return None, None
            parts = [p.strip() for p in val.split(",")]
            if len(parts) != 2:
                return None, None
            try:
                return float(parts[0]), float(parts[1])
            except (ValueError, TypeError):
                return None, None
        pairs = df[LOCAL_LATLONG_SINGLE_COL].apply(split_latlon)
        df = df.copy()
        df["local_lat"] = [p[0] for p in pairs]
        df["local_lon"] = [p[1] for p in pairs]
        return df
    df = df.copy()
    df["local_lat"] = None
    df["local_lon"] = None
    return df


# =========================================================
# 国単位処理
# =========================================================

def process_one_country(excel_path: Path, overseas_map: dict, db: dict):
    country_code = extract_country_code(excel_path)
    if not country_code:
        print(f" skip (no country code): {excel_path.name}")
        return None

    print(f"\n=== processing {country_code} ===")
    placename_dict, records, gdf = get_geonames_for_country(db, country_code, overseas_map)
    print(f" target geonames: {len(records)} records")

    if not placename_dict:
        print(" no geonames data for this country → skip")
        return None

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df = pd.read_excel(excel_path)

    if TARGET_COL not in df.columns:
        print(f" column '{TARGET_COL}' not found → skip")
        return None

    df = ensure_local_lat_lon(df)

    df["normalized_name"] = df[TARGET_COL].astype(str).apply(normalize_comma_abb)
    df[["geonames_hits", "matched_keys"]] = df["normalized_name"].apply(
        lambda xs: pd.Series(match_geonames_candidates(xs, placename_dict))
    )
    df["hit_len"] = df["geonames_hits"].apply(len)
    df["judge"] = df["hit_len"].apply(
        lambda x: "0" if x == 0 else "1" if x == 1 else "2+"
    )

    # 表示用
    df["normalized_candidates"] = df["normalized_name"].apply(
        lambda xs: " | ".join(xs) if isinstance(xs, list) else str(xs)
    )
    df["matched_keys"] = df["matched_keys"].apply(
        lambda xs: " | ".join(xs) if isinstance(xs, list) else str(xs)
    )

    # judge==1 のときは 1件なので、緯度経度・geonameid を列として追加（次の段階用）
    def first_geonameid(hits):
        if not hits or not isinstance(hits, list):
            return None
        return hits[0].get("geonameid") if hits else None

    def first_lat(hits):
        if not hits or not isinstance(hits, list):
            return None
        return hits[0].get("lat") if hits else None

    def first_lon(hits):
        if not hits or not isinstance(hits, list):
            return None
        return hits[0].get("lon") if hits else None

    df["matched_geonameid"] = df["geonames_hits"].apply(first_geonameid)
    df["matched_lat"] = df["geonames_hits"].apply(first_lat)
    df["matched_lon"] = df["geonames_hits"].apply(first_lon)

    out_excel = make_output_excel_name(excel_path)
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["judge"] == "0"].to_excel(writer, sheet_name="judge_0", index=False)
        df[df["judge"] == "1"].to_excel(writer, sheet_name="judge_1", index=False)
        df[df["judge"] == "2+"].to_excel(writer, sheet_name="judge_2plus", index=False)
    print(f" output → {out_excel}")

    total = len(df)
    hit_0 = (df["judge"] == "0").sum()
    hit_1 = (df["judge"] == "1").sum()
    hit_2p = (df["judge"] == "2+").sum()
    return {
        "country": excel_path.stem,
        "total": total,
        "hit_0": hit_0,
        "hit_1": hit_1,
        "hit_2+": hit_2p,
    }


# =========================================================
# メイン
# =========================================================

def main():
    excel_files = sorted(EXCEL_DIR.glob("cn*_*.xlsx"))
    excel_files = [p for p in excel_files if not p.name.startswith("~$")]
    print(f"{len(excel_files)} excel files found")

    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.")

    overseas_map = load_overseas_territories()
    world_stats = []

    for excel_path in excel_files:
        stats = process_one_country(excel_path, overseas_map, db)
        if stats:
            world_stats.append(stats)

    if world_stats:
        df_world = pd.DataFrame(world_stats)
        df_world["hit_2+(%)"] = (df_world["hit_2+"] / df_world["total"] * 100).round(1)
        df_world["hit_1(%)"] = (df_world["hit_1"] / df_world["total"] * 100).round(1)
        df_world["hit_0(%)"] = (df_world["hit_0"] / df_world["total"] * 100).round(1)
        df_world = df_world[
            [
                "country",
                "total",
                "hit_2+",
                "hit_2+(%)",
                "hit_1",
                "hit_1(%)",
                "hit_0",
                "hit_0(%)",
            ]
        ]
        df_world.to_excel(OUTPUT_DIR / "world_stats.xlsx", index=False)
        print("world_stats.xlsx saved")


if __name__ == "__main__":
    main()
