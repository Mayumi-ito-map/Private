"""
司令塔①（合体Excel版）: ローカル候補生成 + GeoNames 完全一致

責務：
- 合体Excel（excel_local_merged/*.xlsx）の「修正後欧文地名」を読む
- normalizers.edit_comma_abb により 1→N 候補生成（略語展開あり）
- Phase1: [name]で完全一致 → インメモリ保持
- Phase2: hit-0 のみを [alternatenames]で完全一致 → インメモリ保持（hit-2+ は除外）
- Phase2終了後: マージしたまま Excel 出力

モード:
- 国毎: cc 列で国毎にグループ化、geonames_master.pkl（by_ccode）で国別マッチング
- 全世界（--worldwide）: num で対象行を絞り、geonames_worldwide_terrain.pkl で一括マッチング

※ 出力は国毎に分割せず、合体ファイル単位で出力する（実験・hit_1 増加が目的）
※ Stage1/2/3 は司令塔②の責務
"""

import argparse
import pickle
import sys
from pathlib import Path

# プロジェクトルートをパスに追加（python -m で実行時）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import math
import unicodedata
import pandas as pd
import warnings

from geonames_loader import load_master_pkl, get_geonames_for_country, build_placename_dict
from normalizers.edit_comma_abb import edit_comma_abb

# =========================================================
# パス設定
# =========================================================

BASE_DIR = PROJECT_ROOT
EXCEL_DIR = BASE_DIR / "excel_local_merged"
OVERSEAS_JSON = BASE_DIR / "config" / "overseas_territories.json"
OUTPUT_DIR = BASE_DIR / "output_match"
OUTPUT_NAME_DIR = BASE_DIR / "output_match_name_cate_CN_固有名詞"
OUTPUT_ALTERNATE_DIR = BASE_DIR / "output_match_alternatenames_CN_固有名詞"
OUTPUT_WORLDWIDE_DIR = BASE_DIR / "output_match_worldwide_distance"
STATS_FILENAME = "tower1_world_stats_CN_固有名詞.xlsx"

# 全世界モード用
TERRAIN_PKL = BASE_DIR / "geonames_worldwide_terrain.pkl"
NUM_FOR_WORLDWIDE_MATCHING = {
    401, 402, 403, 404, 405, 406, 407, 414, 415, 419, 424, 425, 426,
    481, 482, 483, 484, 485, 486, 487, 488, 491, 492,
}

TARGET_COL = "修正後欧文地名"  # Excel の地名列。ローマナイズ

# ローカル緯度経度（Leaflet・距離計測用）。Excelに無ければ欠損のまま出力。
LOCAL_LAT_LON_COLUMNS = [
    ("lat", "long"),
    ("latitude", "longitude"),
    ("緯度", "経度"),
]
LOCAL_LATLONG_SINGLE_COL = "lat,long"

# =========================================================
# カテゴリ制限（fcl フィルタ） #←ここを切り替え
# =========================================================
# local_fcl ごとに ON/OFF と GeoNames の許容 fcl を設定。
# enabled=False にするとそのカテゴリはフィルタなし（制限なしの比較用）。True
FCL_FILTERS = {
    "P": {"enabled": False, "gn_allowed": ("P",)},           # 都市
    "A": {"enabled": False, "gn_allowed": ("A", "L")},      # 地域・エリア
    "S": {"enabled": False, "gn_allowed": ("S", "V")},      # ポイント
    "T": {"enabled": False,  "gn_allowed": ("H", "T")},     # 自然（memo/260304/local_fcl_T_GeoNames_fcl制限_報告書.md）
}

# 合体ファイルのパターン #←ここを切り替え（テスト時は1件のみにすると高速）
MERGED_PATTERNS = [
    # "cn000_asia.xlsx",
    # "cn100_europe.xlsx",
    # "cn200_africa.xlsx",
    # "国立公園.xlsx",
    # "cn300_america.xlsx",
    # "cn450_oceania.xlsx",
    # "cn026_KR-KP_asia.xlsx",
    "cn028_CN_asia.xlsx",
    # "cn001_JP_日本.xlsx",
]

# 削除フラグ列（"1" の行はマッチング対象から除外）
EXCLUDE_COL = "exclude"

# 距離閾値（km）。None はフィルタなし。カテゴリ別に変更可能。
DISTANCE_THRESHOLDS = {
    "P": 150,
    "A": 500,
    "S": 10,
    "T": None,
}
# 閾値フィルタの ON/OFF。False でフィルタなし。True
ENABLE_DISTANCE_THRESHOLD = True

# =========================================================
# 海外領土ロード
# =========================================================

def load_overseas_territories():
    if not OVERSEAS_JSON.exists():
        return {}
    with open(OVERSEAS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _to_int(val):
    """num 列の値を int に変換（Excel の float 等に対応）。"""
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# =========================================================
# GeoNamesヒット判定（geonameid ユニーク化）
# =========================================================
# 候補名リストを placename_dict（名前→レコード）で完全一致検索。
# 複数候補で同一 geonameid がヒットした場合は1件にまとめる。

def match_geonames_candidates(candidates: list, placename_dict: dict):
    """
    candidates: 正規化後の地名候補リスト
    placename_dict: 名前 -> [record, ...]
    返値: (unique_hits, matched_keys)
    """
    hits = []
    matched_keys = []
    for name in candidates:
        key = unicodedata.normalize("NFC", name) if name else ""
        if key and key in placename_dict:
            hits.extend(placename_dict[key])
            matched_keys.append(name)

    unique = {}
    for r in hits:
        geoid = r.get("geonameid")
        if geoid:
            unique[geoid] = r
    return list(unique.values()), matched_keys


# =========================================================
# 距離計算（Haversine）
# =========================================================

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の大圏距離（km）を計算。"""
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _calc_distance_row(lat1, lon1, lat2, lon2) -> float | None:
    """1対の緯度経度から距離（km）を計算。欠損なら None。"""
    try:
        la1, lo1 = float(lat1), float(lon1)
        la2, lo2 = float(lat2), float(lon2)
    except (TypeError, ValueError):
        return None
    if math.isnan(la1) or math.isnan(lo1) or math.isnan(la2) or math.isnan(lo2):
        return None
    return round(_haversine_km(la1, lo1, la2, lo2), 2)


# =========================================================
# ローカル緯度経度の正規化
# =========================================================

def ensure_local_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    """Excel の lat/lon を local_lat / local_lon に統一。"""
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
# マッチング列追加（Phase1用）
# =========================================================

def _add_match_columns(
    df: pd.DataFrame,
    placename_dict: dict,
    hits_col: str = "geonames_hits",
) -> pd.DataFrame:
    """
    edited_name（略語展開後の候補リスト）に対してマッチングし、
    hits_col, judge, fcl, fcode, distance, matched_geonameid 等を追加。
    matched_* は全候補を " | " 区切りで出力（1件なら1件、複数なら全部）。
    """
    df = df.copy()
    df[[hits_col, "matched_keys"]] = df["edited_name"].apply(
        lambda xs: pd.Series(match_geonames_candidates(xs, placename_dict))
    )

    # -------------------------------------------------------------------------
    # [fcl フィルタ] FCL_FILTERS に従い、lo_fcl ごとに GeoNames ヒットを限定
    # -------------------------------------------------------------------------
    if "lo_fcl" in df.columns:
        for lo_fcl, cfg in FCL_FILTERS.items():
            if not cfg.get("enabled"):
                continue
            gn_allowed = tuple(cfg.get("gn_allowed", ()))
            if not gn_allowed:
                continue

            def _filter_hits(row, _hits_col=hits_col, _gn_allowed=gn_allowed, _lo_fcl=lo_fcl):
                hits = row[_hits_col]
                if row.get("lo_fcl") != _lo_fcl or not hits:
                    return row[_hits_col], row["matched_keys"]
                filtered = [r for r in hits if r.get("fcl", "") in _gn_allowed]
                hit_ids = {r.get("geonameid") for r in filtered if r.get("geonameid")}
                candidates = row["edited_name"]
                if not isinstance(candidates, list):
                    candidates = [candidates] if candidates else []
                result_keys = []
                for name in candidates:
                    key = unicodedata.normalize("NFC", name) if name else ""
                    if key and key in placename_dict:
                        for r in placename_dict[key]:
                            if r.get("geonameid") in hit_ids:
                                result_keys.append(name)
                                break
                return filtered, result_keys

            mask = df["lo_fcl"] == lo_fcl
            if mask.any():
                res = df.loc[mask].apply(_filter_hits, axis=1)
                for i, idx in enumerate(df.index[mask]):
                    df.at[idx, hits_col] = res.iloc[i][0]
                    df.at[idx, "matched_keys"] = res.iloc[i][1]

    df["hit_len"] = df[hits_col].apply(len)
    df["judge"] = df["hit_len"].apply(
        lambda x: "0" if x == 0 else "1" if x == 1 else "2+"
    )
    df["edited_candidates"] = df["edited_name"].apply(
        lambda xs: " | ".join(xs) if isinstance(xs, list) else str(xs)
    )
    df["matched_keys"] = df["matched_keys"].apply(
        lambda xs: " | ".join(xs) if isinstance(xs, list) else str(xs)
    )

    # fcl, fcode: 候補ごとに縦棒区切り
    def _join_fcl(hits):
        if not hits or not isinstance(hits, list):
            return ""
        return " | ".join(str(r.get("fcl", "")) for r in hits)

    def _join_fcode(hits):
        if not hits or not isinstance(hits, list):
            return ""
        return " | ".join(str(r.get("fcode", "")) for r in hits)

    df["fcl"] = df[hits_col].apply(_join_fcl)
    df["fcode"] = df[hits_col].apply(_join_fcode)

    # distance, matched_*: 全候補を " | " 区切りで出力（1件なら1件、複数なら全部）
    def _calc_dist_and_best(row):
        hits = row[hits_col]
        lat1, lon1 = row.get("local_lat"), row.get("local_lon")
        if not hits or not isinstance(hits, list):
            return "", None, None, None

        def _safe(v):
            return "" if v is None else str(v)

        geonameids = " | ".join(_safe(r.get("geonameid")) for r in hits)
        lats = " | ".join(_safe(r.get("lat")) for r in hits)
        lons = " | ".join(_safe(r.get("lon")) for r in hits)

        if pd.isna(lat1) or pd.isna(lon1):
            return "", geonameids, lats, lons

        distances = []
        for r in hits:
            d = _calc_distance_row(lat1, lon1, r.get("lat"), r.get("lon"))
            distances.append(d if d is not None else float("inf"))
        dist_str = " | ".join(
            str(round(d, 2)) if d != float("inf") else "" for d in distances
        )
        return dist_str, geonameids, lats, lons

    res = df.apply(_calc_dist_and_best, axis=1)
    df["distance"] = [r[0] for r in res]
    df["matched_geonameid"] = [r[1] for r in res]
    df["matched_lat"] = [r[2] for r in res]
    df["matched_lon"] = [r[3] for r in res]
    return df


# =========================================================
# 候補数・行数カウント
# =========================================================

def _count_candidates(df: pd.DataFrame) -> int:
    """全行の edited_name の候補数の合計。"""
    def cnt(xs):
        if isinstance(xs, list):
            return len(xs)
        return 1 if xs else 0
    return df["edited_name"].apply(cnt).sum()


def _count_candidates_for_judge(df: pd.DataFrame, judge_val: str, judge_col: str = "judge") -> int:
    """judge が judge_val の行の候補数合計。"""
    if judge_col not in df.columns:
        return 0
    mask = df[judge_col] == judge_val
    sub = df.loc[mask, "edited_name"]
    def cnt(xs):
        if isinstance(xs, list):
            return len(xs)
        return 1 if xs else 0
    return sub.apply(cnt).sum()


# =========================================================
# Phase 1: name でマッチング（インメモリ保持）
# =========================================================

def process_one_country_phase1(
    df: pd.DataFrame,
    country_code: str,
    overseas_map: dict,
    db: dict,
    use_abbreviation: bool = True,
):
    """
    Phase1: GeoNames の [name] フィールドで完全一致マッチング。
    geonames_loader は by_cc（または by_ccode）から国別レコードを取得し、
    build_placename_dict で名前→レコード辞書を構築する。
    """
    placename_dict, records, _ = get_geonames_for_country(
        db, country_code, overseas_map, field="name"
    )

    if TARGET_COL not in df.columns:
        return None, None

    # NFC 正規化（Excel 読み込み直後。Unicode 表記ゆれを吸収）
    df = df.copy()
    df[TARGET_COL] = df[TARGET_COL].astype(str).apply(
        lambda x: unicodedata.normalize("NFC", x) if pd.notna(x) and x else x
    )

    df = ensure_local_lat_lon(df)
    # 略語展開: 1地名 → N候補（カンマ並び替え・略語変換表適用）
    df["edited_name"] = df[TARGET_COL].apply(
        lambda x: edit_comma_abb(x, use_abbreviation=use_abbreviation)
    )
    df = _add_match_columns(df, placename_dict, hits_col="geonames_name_hits")

    # Phase1 用列名（run_stage_match 等との互換のため hit_name_len, name_judge）
    df = df.rename(columns={"hit_len": "hit_name_len", "judge": "name_judge"})

    total_row = len(df)
    total_candidate = _count_candidates(df)
    hit_name_1_row = (df["name_judge"] == "1").sum()
    hit_name_2p_row = (df["name_judge"] == "2+").sum()
    hit_name_0_row = (df["name_judge"] == "0").sum()
    hit_name_1_candidate = _count_candidates_for_judge(df, "1", judge_col="name_judge")
    hit_name_2p_candidate = _count_candidates_for_judge(df, "2+", judge_col="name_judge")
    hit_name_0_candidate = _count_candidates_for_judge(df, "0", judge_col="name_judge")

    # 統計の country: cn 列があれば "cn101_IS" 形式（以前の cn002_AZ_アゼルバイジャン に近い）
    cn_val = str(df["cn"].iloc[0]).strip() if "cn" in df.columns and len(df) > 0 else ""
    country_label = f"{cn_val}_{country_code}" if cn_val else country_code

    stats = {
        "country": country_label,
        "total_row": total_row,
        "total_candidate": total_candidate,
        "hit_name_1_row": hit_name_1_row,
        "hit_name_2p_row": hit_name_2p_row,
        "hit_name_0_row": hit_name_0_row,
        "hit_name_1_candidate": hit_name_1_candidate,
        "hit_name_2p_candidate": hit_name_2p_candidate,
        "hit_name_0_candidate": hit_name_0_candidate,
    }
    return df, stats


# =========================================================
# Phase 2: alternatenames でマッチング（インメモリ保持）
# =========================================================

def process_one_country_phase2(
    df_phase1: pd.DataFrame,
    country_code: str,
    overseas_map: dict,
    db: dict,
):
    """
    Phase2: Phase1 で hit-name-0 だった行のみ、[alternatenames] で再マッチング。
    hit-name-2+ は除外（Phase1 で既に複数候補のため）。
    """
    if df_phase1 is None or len(df_phase1) == 0:
        return None, {}

    placename_dict, records, _ = get_geonames_for_country(
        db, country_code, overseas_map, field="alternatenames"
    )

    # Phase2 対象: name_judge が "0" のみ（hit-2+ は Phase1 で確定のため除外）
    df_target = df_phase1[df_phase1["name_judge"] == "0"].copy()
    if len(df_target) == 0:
        return None, {}

    df_target = _add_match_columns(
        df_target, placename_dict, hits_col="geonames_alternatenames_hits"
    )
    df_target = df_target.rename(
        columns={"hit_len": "hit_alter_len", "judge": "alter_judge"}
    )
    df_target["matched_stage"] = df_target.apply(
        lambda r: "hit-alter-1" if r["alter_judge"] == "1" else "hit-alter-2+" if r["alter_judge"] == "2+" else "",
        axis=1
    )
    df_target["matched"] = df_target["alter_judge"].isin(("1", "2+"))

    stats = {
        "phase2_target_row": len(df_target),
        "phase2_target_candidate": _count_candidates(df_target),
        "hit_alter_1_row": (df_target["alter_judge"] == "1").sum(),
        "hit_alter_2p_row": (df_target["alter_judge"] == "2+").sum(),
        "hit_alter_0_row": (df_target["alter_judge"] == "0").sum(),
        "hit_alter_1_candidate": _count_candidates_for_judge(df_target, "1", "alter_judge"),
        "hit_alter_2p_candidate": _count_candidates_for_judge(df_target, "2+", "alter_judge"),
        "hit_alter_0_candidate": _count_candidates_for_judge(df_target, "0", "alter_judge"),
    }
    return df_target, stats


def _zero_stats_phase2() -> dict:
    return {
        "phase2_target_row": 0, "phase2_target_candidate": 0,
        "hit_alter_1_row": 0, "hit_alter_2p_row": 0, "hit_alter_0_row": 0,
        "hit_alter_1_candidate": 0, "hit_alter_2p_candidate": 0, "hit_alter_0_candidate": 0,
    }


def _recalc_stats_from_merged_df(df: pd.DataFrame, country_label: str) -> dict:
    """
    マージ済み df（閾値フィルタ適用後）から統計を再計算。
    ENABLE_DISTANCE_THRESHOLD 適用時に、統計表の数字を正しく反映するため。
    """
    total_row = len(df)
    total_candidate = _count_candidates(df)
    hit_name_1_row = (df["name_judge"] == "1").sum()
    hit_name_2p_row = (df["name_judge"] == "2+").sum()
    hit_name_0_row = (df["name_judge"] == "0").sum()
    hit_name_1_candidate = _count_candidates_for_judge(df, "1", judge_col="name_judge")
    hit_name_2p_candidate = _count_candidates_for_judge(df, "2+", judge_col="name_judge")
    hit_name_0_candidate = _count_candidates_for_judge(df, "0", judge_col="name_judge")

    df_target = df[df["name_judge"] == "0"] if "name_judge" in df.columns else pd.DataFrame()
    phase2_target_row = len(df_target)
    phase2_target_candidate = _count_candidates(df_target) if len(df_target) > 0 else 0
    hit_alter_1_row = (df_target["alter_judge"] == "1").sum() if "alter_judge" in df_target.columns and len(df_target) > 0 else 0
    hit_alter_2p_row = (df_target["alter_judge"] == "2+").sum() if "alter_judge" in df_target.columns and len(df_target) > 0 else 0
    # alter_judge が None の行: 距離閾値で name を 0 にした行（Phase2 未実行）。hit-alter-0 に含める
    hit_alter_0_row = (
        ((df_target["alter_judge"] == "0") | (df_target["alter_judge"].isna())).sum()
        if "alter_judge" in df_target.columns and len(df_target) > 0 else 0
    )
    hit_alter_1_candidate = _count_candidates_for_judge(df_target, "1", "alter_judge") if len(df_target) > 0 else 0
    hit_alter_2p_candidate = _count_candidates_for_judge(df_target, "2+", "alter_judge") if len(df_target) > 0 else 0
    hit_alter_0_candidate = _count_candidates_for_judge(df_target, "0", "alter_judge") if len(df_target) > 0 else 0

    return {
        "country": country_label,
        "total_row": total_row,
        "total_candidate": total_candidate,
        "hit_name_1_row": hit_name_1_row,
        "hit_name_2p_row": hit_name_2p_row,
        "hit_name_0_row": hit_name_0_row,
        "hit_name_1_candidate": hit_name_1_candidate,
        "hit_name_2p_candidate": hit_name_2p_candidate,
        "hit_name_0_candidate": hit_name_0_candidate,
        "phase2_target_row": phase2_target_row,
        "phase2_target_candidate": phase2_target_candidate,
        "hit_alter_1_row": hit_alter_1_row,
        "hit_alter_2p_row": hit_alter_2p_row,
        "hit_alter_0_row": hit_alter_0_row,
        "hit_alter_1_candidate": hit_alter_1_candidate,
        "hit_alter_2p_candidate": hit_alter_2p_candidate,
        "hit_alter_0_candidate": hit_alter_0_candidate,
    }


# =========================================================
# Phase2 の結果を Phase1 にマージ（hit-0 行のみ Phase2 列で上書き）
# =========================================================

def _merge_phase2_into_phase1(df_phase1: pd.DataFrame, df_phase2: pd.DataFrame) -> pd.DataFrame:
    """
    Phase1 の全行をベースに、Phase2 対象（hit-name-0）行の列を Phase2 結果で更新する。
    Phase2 対象外の行は Phase2 列を空欄にする（マージ時の抜け防止のため全行を保持）。
    """
    df_out = df_phase1.copy()

    # Phase2 列（alternate 用）を常に追加。df_phase2 が空なら全行空欄
    phase2_cols = [
        "geonames_alternatenames_hits", "hit_alter_len", "alter_judge",
        "matched_stage", "matched",
    ]
    for col in phase2_cols:
        if col not in df_out.columns:
            df_out[col] = None

    if df_phase2 is not None and len(df_phase2) > 0:
        for col in df_phase2.columns:
            if col not in df_out.columns:
                df_out[col] = None
        for col in df_phase2.columns:
            df_out.loc[df_phase2.index, col] = df_phase2[col].values

    return df_out


def _compute_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    matched_stage, judge, matched を最終状態で設定する。
    name_judge / alter_judge の結果を統合し、1つの判定に集約する。
    """
    df = df.copy()

    def _final(row):
        nj = str(row.get("name_judge", "0")).strip() if pd.notna(row.get("name_judge")) else "0"
        aj = str(row.get("alter_judge", "")).strip() if pd.notna(row.get("alter_judge")) else ""
        if nj in ("1", "2+"):
            return f"hit-name-{nj}", nj, True
        if aj in ("1", "2+"):
            return f"hit-alter-{aj}", aj, True
        return "", "0", False

    results = df.apply(_final, axis=1, result_type="expand")
    df["matched_stage"] = results[0]
    df["judge"] = results[1]
    df["matched"] = results[2]
    return df


def _parse_distance_list(dist_val):
    """distance 列をリストに変換。' | ' 区切り。無効値は float('inf') で返す。"""
    if pd.isna(dist_val) or dist_val == "":
        return []
    parts = str(dist_val).replace(",", "").split(" | ")
    vals = []
    for p in parts:
        p = p.strip()
        if not p:
            vals.append(float("inf"))
            continue
        try:
            vals.append(float(p))
        except (ValueError, TypeError):
            vals.append(float("inf"))
    return vals


def _apply_distance_threshold_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    距離閾値で候補を絞り込み。
    閾値超過の候補を除外し、残りが1件なら hit-1、2件以上なら hit-2+、0件なら hit-0 に更新。
    """
    if "lo_fcl" not in df.columns or "distance" not in df.columns:
        return df
    df = df.copy()
    n_changed = 0
    for idx, row in df.iterrows():
        lo_fcl = row.get("lo_fcl")
        if pd.isna(lo_fcl):
            continue
        lo_fcl = str(lo_fcl).strip()
        th = DISTANCE_THRESHOLDS.get(lo_fcl)
        if th is None:
            continue

        # name  phase か alter phase かを判定
        if row.get("name_judge") in ("1", "2+"):
            hits_col = "geonames_name_hits"
            judge_col = "name_judge"
            len_col = "hit_name_len"
            is_alter = False
        elif row.get("alter_judge") in ("1", "2+"):
            hits_col = "geonames_alternatenames_hits"
            judge_col = "alter_judge"
            len_col = "hit_alter_len"
            is_alter = True
        else:
            continue

        hits = row.get(hits_col)
        if not hits or not isinstance(hits, list):
            continue
        distances = _parse_distance_list(row.get("distance"))
        if not distances:
            continue  # local の lat/lon が無く距離計算不可 → フィルタ対象外
        if len(distances) != len(hits):
            distances = distances[:len(hits)] if len(distances) > len(hits) else distances + [float("inf")] * (len(hits) - len(distances))

        # 閾値以内の候補のみ残す
        kept = [(r, d) for r, d in zip(hits, distances) if d <= th]
        if len(kept) == len(hits):
            continue  # 変更なし

        n_changed += 1
        kept_hits = [x[0] for x in kept]
        kept_dists = [x[1] for x in kept]

        def _safe(v):
            return "" if v is None else str(v)

        if len(kept) == 0:
            # hit-0
            df.at[idx, hits_col] = []
            df.at[idx, len_col] = 0
            df.at[idx, judge_col] = "0"
            df.at[idx, "fcl"] = ""
            df.at[idx, "fcode"] = ""
            df.at[idx, "distance"] = ""
            df.at[idx, "matched_geonameid"] = None
            df.at[idx, "matched_lat"] = None
            df.at[idx, "matched_lon"] = None
            if is_alter:
                df.at[idx, "matched_stage"] = ""
                df.at[idx, "matched"] = False
            if "matched_keys" in df.columns:
                df.at[idx, "matched_keys"] = ""
        else:
            # 絞り込み後 1件 or 2+件
            df.at[idx, hits_col] = kept_hits
            df.at[idx, len_col] = len(kept_hits)
            df.at[idx, judge_col] = "1" if len(kept_hits) == 1 else "2+"
            df.at[idx, "fcl"] = " | ".join(str(r.get("fcl", "")) for r in kept_hits)
            df.at[idx, "fcode"] = " | ".join(str(r.get("fcode", "")) for r in kept_hits)
            df.at[idx, "distance"] = " | ".join(str(round(d, 2)) if d != float("inf") else "" for d in kept_dists)
            df.at[idx, "matched_geonameid"] = " | ".join(_safe(r.get("geonameid")) for r in kept_hits)
            df.at[idx, "matched_lat"] = " | ".join(_safe(r.get("lat")) for r in kept_hits)
            df.at[idx, "matched_lon"] = " | ".join(_safe(r.get("lon")) for r in kept_hits)
            if is_alter:
                df.at[idx, "matched_stage"] = "hit-alter-1" if len(kept_hits) == 1 else "hit-alter-2+"
                df.at[idx, "matched"] = True

    if n_changed > 0:
        print(f"  距離閾値で絞り込み: {n_changed} 行")
    return df


# =========================================================
# 列順序の整列（local_lon の右に GeoNames: fcl, fcode, edited_name, ...）
# =========================================================

# GeoNames マージ列の順序: local_lon の直後に fcl, fcode, edited_name, geonames_name_hits, ...
GEONAMES_MERGE_ORDER = [
    "fcl",
    "fcode",
    "distance",
    "edited_name",
    "geonames_name_hits",
    "matched_keys",
    "hit_name_len",
    "name_judge",
    "edited_candidates",
    "matched_geonameid",
    "matched_lat",
    "matched_lon",
    # Phase2
    "geonames_alternatenames_hits",
    "hit_alter_len",
    "alter_judge",
    "matched_stage",
    "matched",
    "judge",
]


def _reorder_columns_for_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    出力用に列順を整える。
    - local_lat, local_lon の直後に GeoNames: fcl, fcode, edited_name, geonames_name_hits, ...
    """
    cols = list(df.columns)
    ordered = []
    # 1. GeoNames マージ列以外（local_lat/lon 除く）を元の順で
    for c in cols:
        if c not in GEONAMES_MERGE_ORDER and c not in ("local_lat", "local_lon"):
            ordered.append(c)
    # 2. local_lat, local_lon（local_lon の右に fcl を置くため、その直前に配置）
    for c in ("local_lat", "local_lon"):
        if c in cols:
            ordered.append(c)
    # 3. GeoNames 列を指定順で
    for c in GEONAMES_MERGE_ORDER:
        if c in cols:
            ordered.append(c)
    # 4. 残り
    for c in cols:
        if c not in ordered:
            ordered.append(c)
    return df[[c for c in ordered]]


# =========================================================
# Excel 出力（マージファイル単位）
# =========================================================

def _write_phase1_excel(df: pd.DataFrame, base: str, output_name_dir: Path) -> None:
    """Phase1 結果を *_name.xlsx に出力。"""
    if df is None or len(df) == 0:
        return
    df = _compute_final_columns(df.copy())
    df = _reorder_columns_for_output(df)
    output_name_dir.mkdir(parents=True, exist_ok=True)
    out_excel = output_name_dir / f"{base}_name.xlsx"
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["name_judge"] == "0"].to_excel(writer, sheet_name="judge_0", index=False)
        df[df["name_judge"] == "1"].to_excel(writer, sheet_name="judge_1", index=False)
        df[df["name_judge"] == "2+"].to_excel(writer, sheet_name="judge_2plus", index=False)
    print(f"  output → {out_excel.name}")


def _write_phase2_excel(df: pd.DataFrame, base: str, output_alternate_dir: Path) -> None:
    """Phase2 結果を *_alternate.xlsx に出力。全行を出力し、Phase2 対象外は alternate 列を空欄。"""
    if df is None or len(df) == 0:
        return
    df = _compute_final_columns(df.copy())
    df = _reorder_columns_for_output(df)
    output_alternate_dir.mkdir(parents=True, exist_ok=True)
    out_excel = output_alternate_dir / f"{base}_alternate.xlsx"
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["alter_judge"] == "0"].to_excel(writer, sheet_name="judge_0", index=False)
        df[df["alter_judge"] == "1"].to_excel(writer, sheet_name="judge_1", index=False)
        df[df["alter_judge"] == "2+"].to_excel(writer, sheet_name="judge_2plus", index=False)
    print(f"  output → {out_excel.name}")


# =========================================================
# 統計表の構築・保存
# =========================================================

def _build_tower1_stats(all_stats: list[dict]) -> pd.DataFrame:
    """Phase1 + Phase2 の統計を結合し、パーセンテージを計算。"""
    rows = []
    for s in all_stats:
        if not s:
            continue
        total_row = s.get("total_row", 0)
        total_can = s.get("total_candidate", 0)
        hit_name_0_row = s.get("hit_name_0_row", 0)
        hit_name_0_can = s.get("hit_name_0_candidate", 0)

        def pct(a, b):
            return round(a / b * 100, 1) if b and b > 0 else 0

        row = {
            "country": s.get("country", ""),
            "total_row": total_row,
            "total_can": total_can,
            "hit-name-1": s.get("hit_name_1_row", 0),
            "hit-name-1_row(%)": pct(s.get("hit_name_1_row", 0), total_row),
            "hit-name-2+_row": s.get("hit_name_2p_row", 0),
            "hit-name-2+_can": s.get("hit_name_2p_candidate", 0),
            "hit-name-2+_can(%)": pct(s.get("hit_name_2p_candidate", 0), total_can),
            "hit-name-0_row": hit_name_0_row,
            "hit-name-0_can": hit_name_0_can,
            "hit-name-0_can(%)": pct(hit_name_0_can, total_can),
            "hit-alter-1": s.get("hit_alter_1_row", 0),
            "hit-alter-1_row(%)": pct(s.get("hit_alter_1_row", 0), hit_name_0_row),
            "hit-alter-2+_row": s.get("hit_alter_2p_row", 0),
            "hit-alter-2+_can": s.get("hit_alter_2p_candidate", 0),
            "hit-alter-2+_can(%)": pct(s.get("hit_alter_2p_candidate", 0), hit_name_0_can),
            "hit-alter-0+_row": s.get("hit_alter_0_row", 0),
            "hit-alter-0+_can": s.get("hit_alter_0_candidate", 0),
            "hit-alter-0_can(%)": pct(s.get("hit_alter_0_candidate", 0), hit_name_0_can),
        }
        rows.append(row)
    return pd.DataFrame(rows)


# =========================================================
# 全世界モード（Phase1/Phase2 を geonames_worldwide_terrain.pkl で実行）
# =========================================================

def _process_worldwide_one_file(
    merged_path: Path,
    placename_dict_name: dict,
    placename_dict_alternatenames: dict,
) -> pd.DataFrame | None:
    """1つの合体 Excel を処理。num で対象行を絞り、Phase1 + Phase2 を実行。"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df_all = pd.read_excel(merged_path)

    if "fcl" in df_all.columns:
        df_all = df_all.rename(columns={"fcl": "lo_fcl"})

    if "num" not in df_all.columns:
        print(f"  skip: num 列がありません")
        return None

    df_all["_num_int"] = df_all["num"].apply(_to_int)
    df = df_all[df_all["_num_int"].isin(NUM_FOR_WORLDWIDE_MATCHING)].copy()
    df = df.drop(columns=["_num_int"], errors="ignore")

    # exclude フラグ「1」の行を除外
    if EXCLUDE_COL in df.columns:
        def _is_excluded(val):
            if pd.isna(val):
                return False
            s = str(val).strip()
            return s == "1" or s == "1.0"
        mask_exclude = df[EXCLUDE_COL].apply(_is_excluded)
        n_excluded = mask_exclude.sum()
        if n_excluded > 0:
            df = df[~mask_exclude].copy()
            print(f"  exclude 除外: {n_excluded} 行")

    if len(df) == 0:
        print(f"  対象行なし")
        return None

    print(f"  対象行: {len(df)}")

    if TARGET_COL not in df.columns:
        print(f"  skip: {TARGET_COL} がありません")
        return None

    df = df.copy()
    df[TARGET_COL] = df[TARGET_COL].astype(str).apply(
        lambda x: unicodedata.normalize("NFC", x) if pd.notna(x) and x else x
    )
    df = ensure_local_lat_lon(df)
    df["edited_name"] = df[TARGET_COL].apply(lambda x: edit_comma_abb(x, use_abbreviation=True))

    # Phase1: name で完全一致
    df_p1 = _add_match_columns(df, placename_dict_name, hits_col="geonames_name_hits")
    df_p1 = df_p1.rename(columns={"hit_len": "hit_name_len", "judge": "name_judge"})
    df_p1["matched_source"] = df_p1["name_judge"].apply(
        lambda j: "worldwide_phase1" if j != "0" else ""
    )

    # Phase1 → 距離フィルタ → Phase2 → 距離フィルタ の順で適用
    if ENABLE_DISTANCE_THRESHOLD:
        df_p1 = _apply_distance_threshold_filter(df_p1)

    # Phase2: フィルタ後の hit-0 のみ alternatenames で完全一致
    df_target = df_p1[df_p1["name_judge"] == "0"].copy()
    if len(df_target) > 0:
        df_p2 = _add_match_columns(
            df_target, placename_dict_alternatenames, hits_col="geonames_alternatenames_hits"
        )
        df_p2 = df_p2.rename(columns={"hit_len": "hit_alter_len", "judge": "alter_judge"})
        df_p2["matched_stage"] = df_p2.apply(
            lambda r: "hit-alter-1" if r["alter_judge"] == "1" else "hit-alter-2+" if r["alter_judge"] == "2+" else "",
            axis=1
        )
        df_p2["matched_source"] = df_p2["alter_judge"].apply(
            lambda j: "worldwide_phase2" if j != "0" else ""
        )
        df_p2["matched"] = df_p2["alter_judge"].isin(("1", "2+"))
        df_out = _merge_phase2_into_phase1(df_p1, df_p2)
    else:
        df_out = df_p1.copy()
        for col in ["geonames_alternatenames_hits", "hit_alter_len", "alter_judge", "matched_stage", "matched", "matched_source"]:
            if col not in df_out.columns:
                df_out[col] = None

    if ENABLE_DISTANCE_THRESHOLD:
        df_out = _apply_distance_threshold_filter(df_out)
    return df_out


def main_worldwide():
    """全世界モード: geonames_worldwide_terrain.pkl で Phase1/Phase2 を一括実行。"""
    if not TERRAIN_PKL.exists():
        print(f"{TERRAIN_PKL} が見つかりません。")
        print("先に build_geonames_worldwide_terrain.py を実行してください。")
        return

    merged_files = [EXCEL_DIR / p for p in MERGED_PATTERNS if (EXCEL_DIR / p).exists()]
    if not merged_files:
        print(f"合体Excelが見つかりません: {EXCEL_DIR}")
        return

    print(f"入力: {EXCEL_DIR}")
    print(f"モード: 全世界（num 対象: {sorted(NUM_FOR_WORLDWIDE_MATCHING)}）")
    print(f"出力: {OUTPUT_WORLDWIDE_DIR}\n")

    print("Loading geonames_worldwide_terrain.pkl ...")
    with open(TERRAIN_PKL, "rb") as f:
        data = pickle.load(f)
    records = data["records"]
    print(f"  {len(records):,} records\n")

    print("Building placename_dict (name) ...")
    placename_dict_name = build_placename_dict(records, field="name")
    print("Building placename_dict (alternatenames) ...")
    placename_dict_alternatenames = build_placename_dict(records, field="alternatenames")

    OUTPUT_WORLDWIDE_DIR.mkdir(parents=True, exist_ok=True)

    for merged_path in merged_files:
        print(f"\n=== {merged_path.name} ===")
        df_out = _process_worldwide_one_file(
            merged_path, placename_dict_name, placename_dict_alternatenames
        )
        if df_out is not None and len(df_out) > 0:
            base = merged_path.stem
            out_path = OUTPUT_WORLDWIDE_DIR / f"{base}_terrain_phase1_2.xlsx"
            df_out = _compute_final_columns(df_out.copy())
            df_out = _reorder_columns_for_output(df_out)
            df_out.to_excel(out_path, index=False)
            print(f"  -> {out_path.name}")

    print("\nDone.")


# =========================================================
# メイン
# =========================================================

def main():
    merged_files = [EXCEL_DIR / p for p in MERGED_PATTERNS if (EXCEL_DIR / p).exists()]
    if not merged_files:
        print(f"合体Excelが見つかりません: {EXCEL_DIR}")
        print(f"  期待: {MERGED_PATTERNS}")
        return

    print(f"入力: {EXCEL_DIR}")
    print(f"対象: {[p.name for p in merged_files]}\n")

    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.\n")

    overseas_map = load_overseas_territories()
    all_stats = []
    all_df_out = []  # tower1_world_stats 全行出力用

    for merged_path in merged_files:
        # 出力ファイル名: cn300_北中アメリカ.xlsx → cn300_北中アメリカ
        merged_base = merged_path.stem

        print(f"\n=== {merged_path.name} ===")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
            df_all = pd.read_excel(merged_path)

        # local の fcl（Excel の num 由来）を lo_fcl にリネーム（GeoNames の fcl と区別）
        if "fcl" in df_all.columns:
            df_all = df_all.rename(columns={"fcl": "lo_fcl"})

        # exclude フラグ「1」の行をマッチング対象から除外
        if EXCLUDE_COL in df_all.columns:
            def _is_excluded(val):
                if pd.isna(val):
                    return False
                s = str(val).strip()
                return s == "1" or s == "1.0"
            mask_exclude = df_all[EXCLUDE_COL].apply(_is_excluded)
            n_excluded = mask_exclude.sum()
            if n_excluded > 0:
                df_all = df_all[~mask_exclude].copy()
                print(f"  exclude 除外: {n_excluded} 行")

        if "cc" not in df_all.columns:
            print("  skip: cc 列がありません")
            continue

        # Phase1 + Phase2: 国毎に処理し、Phase2 を Phase1 にマージしてから結合
        merged_dfs = []

        for cc, df_grp in df_all.groupby("cc", sort=False):
            cc = str(cc).strip()
            if not cc:
                continue

            print(f"\n--- Phase1 (name) {cc} ---")
            placename_dict, records, _ = get_geonames_for_country(db, cc, overseas_map, field="name")
            print(f"  target geonames: {len(records)} records")

            df_p1, stats1 = process_one_country_phase1(
                df_grp.copy(), cc, overseas_map, db, use_abbreviation=True
            )
            if df_p1 is None:
                continue

            all_stats.append(stats1)

            # Phase1 → 距離フィルタ → Phase2 → 距離フィルタ の順で適用
            if ENABLE_DISTANCE_THRESHOLD:
                print(f"--- 距離閾値フィルタ (Phase1 name) {cc} ---")
                df_p1 = _apply_distance_threshold_filter(df_p1)

            # Phase2: フィルタ後の hit-0 のみ alternatenames でマッチング
            print(f"--- Phase2 (alternatenames) {cc} ---")
            df_p2, stats2 = process_one_country_phase2(df_p1, cc, overseas_map, db)
            if stats2:
                all_stats[-1].update(stats2)
            else:
                all_stats[-1].update(_zero_stats_phase2())

            # Phase2 を Phase1 にマージ（国単位）。Phase2 対象外は alternate 列を空欄
            df_merged = _merge_phase2_into_phase1(df_p1, df_p2)
            if ENABLE_DISTANCE_THRESHOLD:
                print(f"--- 距離閾値フィルタ (Phase2 alternate) {cc} ---")
                df_merged = _apply_distance_threshold_filter(df_merged)
                # 閾値フィルタ適用後、統計を再計算して反映
                country_label = all_stats[-1].get("country", cc) if all_stats else cc
                all_stats[-1] = _recalc_stats_from_merged_df(df_merged, country_label)
            merged_dfs.append(df_merged)

        if not merged_dfs:
            continue

        # 全国の結果を結合
        df_out = pd.concat(merged_dfs, ignore_index=True)

        # 出力: マージファイル単位（国毎に分割しない）
        print(f"\n--- Excel 出力 ({merged_base}) ---")
        _write_phase1_excel(df_out, merged_base, OUTPUT_NAME_DIR)

        # _alternate: 全行を出力。Phase2 対象外は alternate 列を空欄（マージ時の抜け防止）
        _write_phase2_excel(df_out, merged_base, OUTPUT_ALTERNATE_DIR)

        # _tower1_world_stats 用に全行を蓄積
        all_df_out.append(df_out)

    # 統計表（tower1_world_stats）: 全行を出力。Phase1/Phase2 と出力形式を揃える
    if all_df_out:
        df_stats_all = pd.concat(all_df_out, ignore_index=True)
        df_stats_all = _compute_final_columns(df_stats_all)
        df_stats_all = _reorder_columns_for_output(df_stats_all)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stats_path = OUTPUT_DIR / STATS_FILENAME
        with pd.ExcelWriter(stats_path, engine="openpyxl") as writer:
            # 統計表を先頭に（tower1_world_stats_統計表.xlsx の形式に合わせる）
            if all_stats:
                stats_df = _build_tower1_stats(all_stats)
                stats_df.to_excel(writer, sheet_name="Sheet1", index=False)
            # 全行を2番目に
            df_stats_all.to_excel(writer, sheet_name="all", index=False)
            if all_stats:
                print(f"\n{stats_path.name} saved (Sheet1: {len(stats_df)} rows, all: {len(df_stats_all)} rows)")
            else:
                print(f"\n{stats_path.name} saved (all: {len(df_stats_all)} rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="司令塔①: GeoNames Phase1/Phase2 完全一致")
    parser.add_argument(
        "--worldwide",
        action="store_true",
        help="全世界モード: geonames_worldwide_terrain.pkl で海・山地名を一括マッチング",
    )
    args = parser.parse_args()

    if args.worldwide:
        main_worldwide()
    else:
        main()
