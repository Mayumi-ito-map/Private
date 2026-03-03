"""
司令塔① : ローカル候補生成 + GeoNames（geonames_master.pkl）完全一致

責務：
- ローカルExcelの「修正後欧文地名」を読む
- normalizers.edit_comma_abb により 1→N 候補生成（略語展開あり）
- config/overseas_territories.json を考慮して国コードを解決
- geonames_master.pkl（by_id / by_cc）から地名を取得し、完全一致で判定
- Phase1: [name]で完全一致 → インメモリ保持
- Phase2: hit-0 のみを [alternatenames]で完全一致 → インメモリ保持（hit-2+ は除外）
- Phase2終了後: Excel出力（*_name.xlsx, *_alternate.xlsx, tower1_world_stats.xlsx）

※ Stage1/2/3 は司令塔②の責務
"""

import ast
import json
import math
import unicodedata
import pandas as pd
import warnings
from pathlib import Path

from geonames_loader import load_master_pkl, get_geonames_for_country
from normalizers.edit_comma_abb import edit_comma_abb
from utils import is_excel_lock_file


# =========================================================
# パス設定
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project/
EXCEL_DIR = BASE_DIR / "excel_local"
OVERSEAS_JSON = BASE_DIR / "config" / "overseas_territories.json"
OUTPUT_DIR = BASE_DIR / "output_match"
OUTPUT_NAME_DIR = BASE_DIR / "output_match_name"
OUTPUT_ALTERNATE_DIR = BASE_DIR / "output_match_alternatenames"
STATS_FILENAME = "tower1_world_stats.xlsx"


TARGET_COL = "修正後欧文地名"
NUM_COL = "num"

# ローカル緯度経度（Leaflet・距離計測用）。Excelに無ければ欠損のまま出力。
LOCAL_LAT_LON_COLUMNS = [
    ("lat", "long"),
    ("latitude", "longitude"),
    ("緯度", "経度"),
]
LOCAL_LATLONG_SINGLE_COL = "lat,long"


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
    unique_hits = list(unique.values())
    return unique_hits, matched_keys


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
# 出力Excel名
# =========================================================

def make_output_base(excel_path: Path) -> str:
    """cn002_AZ_アゼルバイジャン_AZE.xlsx → cn002_AZ_アゼルバイジャン"""
    parts = excel_path.stem.split("_")
    return "_".join(parts[:3])


# =========================================================
# edited_name のパース（リスト復元）
# =========================================================

def parse_edited_name(value) -> list:
    """edited_name をリストに変換。"""
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s in ("[]", "None", "nan"):
            return []
        try:
            parsed = ast.literal_eval(s)
            return parsed if isinstance(parsed, list) else [parsed]
        except (ValueError, SyntaxError):
            return [s] if s else []
    return [value] if value else []


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
    """edited_name に対してマッチングし、hits_col, judge, fcl, fcode, distance 等を追加。"""
    df = df.copy()
    df[[hits_col, "matched_keys"]] = df["edited_name"].apply(
        lambda xs: pd.Series(match_geonames_candidates(xs, placename_dict))
    )
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

    # distance, matched_*: 距離計算＋hit-2+ は最小距離候補を採用
    def _calc_dist_and_best(row):
        hits = row[hits_col]
        lat1, lon1 = row.get("local_lat"), row.get("local_lon")
        if not hits or not isinstance(hits, list):
            return "", None, None, None
        if pd.isna(lat1) or pd.isna(lon1):
            return "", hits[0].get("geonameid"), hits[0].get("lat"), hits[0].get("lon")
        distances = []
        for r in hits:
            d = _calc_distance_row(lat1, lon1, r.get("lat"), r.get("lon"))
            distances.append(d if d is not None else float("inf"))
        if all(d == float("inf") for d in distances):
            dist_str = ""
            best = hits[0]
        else:
            min_idx = min(range(len(distances)), key=lambda i: distances[i])
            best = hits[min_idx]
            dist_str = " | ".join(
                str(round(d, 2)) if d != float("inf") else "" for d in distances
            )
        return dist_str, best.get("geonameid"), best.get("lat"), best.get("lon")

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
    excel_path: Path,
    overseas_map: dict,
    db: dict,
    use_abbreviation: bool = True,
):
    """Phase1: name でマッチング。DataFrame と統計を返す（Excel出力なし）。"""
    country_code = extract_country_code(excel_path)
    if not country_code:
        print(f" skip (no country code): {excel_path.name}")
        return None, None

    print(f"\n=== Phase1 (name) {country_code} ===")
    placename_dict, records, _ = get_geonames_for_country(
        db, country_code, overseas_map, field="name"
    )
    print(f" target geonames: {len(records)} records")

    if not placename_dict:
        print(" no geonames data (name) → 全行 hit_0 として処理継続")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df = pd.read_excel(excel_path)

    if TARGET_COL not in df.columns:
        print(f" column '{TARGET_COL}' not found → skip")
        return None, None

    # NFC 正規化（Excel 読み込み直後）
    df = df.copy()
    df[TARGET_COL] = df[TARGET_COL].astype(str).apply(
        lambda x: unicodedata.normalize("NFC", x) if pd.notna(x) and x else x
    )

    df = ensure_local_lat_lon(df)
    df["edited_name"] = df[TARGET_COL].apply(
        lambda x: edit_comma_abb(x, use_abbreviation=use_abbreviation)
    )
    df = _add_match_columns(df, placename_dict, hits_col="geonames_name_hits")

    # Phase1 用列名（hit_name_len, name_judge）
    df = df.rename(columns={"hit_len": "hit_name_len", "judge": "name_judge"})

    total_row = len(df)
    total_candidate = _count_candidates(df)

    hit_name_1_row = (df["name_judge"] == "1").sum()
    hit_name_2p_row = (df["name_judge"] == "2+").sum()
    hit_name_0_row = (df["name_judge"] == "0").sum()

    hit_name_1_candidate = _count_candidates_for_judge(df, "1", judge_col="name_judge")
    hit_name_2p_candidate = _count_candidates_for_judge(df, "2+", judge_col="name_judge")
    hit_name_0_candidate = _count_candidates_for_judge(df, "0", judge_col="name_judge")

    base = make_output_base(excel_path)
    stats = {
        "country": base,
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
    base: str,
    country_code: str,
    overseas_map: dict,
    db: dict,
):
    """Phase2: hit-0 のみを alternatenames でマッチング。DataFrame と統計を返す。hit-2+ は除外。"""
    if df_phase1 is None or len(df_phase1) == 0:
        return None, None

    print(f"\n=== Phase2 (alternatenames) {country_code} ===")
    placename_dict, records, _ = get_geonames_for_country(
        db, country_code, overseas_map, field="alternatenames"
    )
    print(f" target geonames: {len(records)} records")

    if not placename_dict:
        print(" no geonames data (alternatenames) → 全行 hit_0 として処理継続")

    # Phase2 対象: name_judge が "0" のみ（hit-2+ は除外）
    df_target = df_phase1[df_phase1["name_judge"] == "0"].copy()
    if len(df_target) == 0:
        print(" no hit_0 rows → skip")
        return None, _zero_stats_phase2(base)

    # edited_name は既に list のまま（Phase1 から）
    df_target = _add_match_columns(
        df_target, placename_dict, hits_col="geonames_alternatenames_hits"
    )

    # Phase2 用列名
    df_target = df_target.rename(
        columns={"hit_len": "hit_alter_len", "judge": "alter_judge"}
    )

    # matched_stage, matched を追加（Phase2 対象は hit-name-0 のみなので hit-alter-* または 空欄）
    def _matched_stage(row):
        if row["alter_judge"] == "1":
            return "hit-alter-1"
        if row["alter_judge"] == "2+":
            return "hit-alter-2+"
        return ""

    def _matched(row):
        return row["alter_judge"] in ("1", "2+")

    df_target["matched_stage"] = df_target.apply(_matched_stage, axis=1)
    df_target["matched"] = df_target.apply(_matched, axis=1)

    phase2_target_row = len(df_target)
    phase2_target_candidate = _count_candidates(df_target)

    hit_alter_1_row = (df_target["alter_judge"] == "1").sum()
    hit_alter_2p_row = (df_target["alter_judge"] == "2+").sum()
    hit_alter_0_row = (df_target["alter_judge"] == "0").sum()

    hit_alter_1_candidate = _count_candidates_for_judge(df_target, "1", judge_col="alter_judge")
    hit_alter_2p_candidate = _count_candidates_for_judge(df_target, "2+", judge_col="alter_judge")
    hit_alter_0_candidate = _count_candidates_for_judge(df_target, "0", judge_col="alter_judge")

    to_tower2_row = hit_alter_0_row
    to_tower2_candidate = hit_alter_0_candidate

    stats = {
        "phase2_target_row": phase2_target_row,
        "phase2_target_candidate": phase2_target_candidate,
        "hit_alter_1_row": hit_alter_1_row,
        "hit_alter_2p_row": hit_alter_2p_row,
        "hit_alter_0_row": hit_alter_0_row,
        "hit_alter_1_candidate": hit_alter_1_candidate,
        "hit_alter_2p_candidate": hit_alter_2p_candidate,
        "hit_alter_0_candidate": hit_alter_0_candidate,
        "to_tower2_row": to_tower2_row,
        "to_tower2_candidate": to_tower2_candidate,
    }
    return df_target, stats


def _zero_stats_phase2(base: str) -> dict:
    return {
        "phase2_target_row": 0,
        "phase2_target_candidate": 0,
        "hit_alter_1_row": 0,
        "hit_alter_2p_row": 0,
        "hit_alter_0_row": 0,
        "hit_alter_1_candidate": 0,
        "hit_alter_2p_candidate": 0,
        "hit_alter_0_candidate": 0,
        "to_tower2_row": 0,
        "to_tower2_candidate": 0,
    }


# =========================================================
# Excel 出力（Phase2 終了後）
# =========================================================

def _write_phase1_excel(df: pd.DataFrame, base: str, output_name_dir: Path) -> None:
    """Phase1 結果を *_name.xlsx に出力。"""
    if df is None or len(df) == 0:
        return
    output_name_dir.mkdir(parents=True, exist_ok=True)
    out_excel = output_name_dir / f"{base}_name.xlsx"
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["name_judge"] == "0"].to_excel(writer, sheet_name="judge_0", index=False)
        df[df["name_judge"] == "1"].to_excel(writer, sheet_name="judge_1", index=False)
        df[df["name_judge"] == "2+"].to_excel(writer, sheet_name="judge_2plus", index=False)
    print(f" output → {out_excel}")


def _write_phase2_excel(df: pd.DataFrame, base: str, output_alternate_dir: Path) -> None:
    """Phase2 結果を *_alternate.xlsx に出力。Phase2 対象行のみ（hit-name-0）。"""
    if df is None or len(df) == 0:
        return
    output_alternate_dir.mkdir(parents=True, exist_ok=True)
    out_excel = output_alternate_dir / f"{base}_alternate.xlsx"
    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)
        df[df["alter_judge"] == "0"].to_excel(writer, sheet_name="judge_0", index=False)
        df[df["alter_judge"] == "1"].to_excel(writer, sheet_name="judge_1", index=False)
        df[df["alter_judge"] == "2+"].to_excel(writer, sheet_name="judge_2plus", index=False)
    print(f" output → {out_excel}")


# =========================================================
# 統計表の構築・保存
# =========================================================

def _build_tower1_stats(all_stats: list[dict]) -> pd.DataFrame:
    """Phase1 + Phase2 の統計を結合し、パーセンテージを計算。"""
    rows = []
    for s in all_stats:
        if s is None:
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
# メイン
# =========================================================

def main():
    excel_files = sorted(EXCEL_DIR.glob("cn*_*.xlsx"))
    excel_files = [p for p in excel_files if not is_excel_lock_file(p)]
    print(f"{len(excel_files)} excel files found")

    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.")

    overseas_map = load_overseas_territories()

    phase1_results = {}
    all_stats = []

    # Phase 1: name でマッチング（略語展開あり）
    print("\n" + "=" * 50)
    print("Phase 1: [name] でマッチング（インメモリ保持）")
    print("=" * 50)
    for excel_path in excel_files:
        base = make_output_base(excel_path)
        df, stats = process_one_country_phase1(
            excel_path, overseas_map, db, use_abbreviation=True
        )
        if df is not None:
            phase1_results[base] = df
        if stats is not None:
            all_stats.append(stats)
        else:
            all_stats.append({
                "country": base,
                "total_row": 0, "total_candidate": 0,
                "hit_name_1_row": 0, "hit_name_2p_row": 0, "hit_name_0_row": 0,
                "hit_name_1_candidate": 0, "hit_name_2p_candidate": 0, "hit_name_0_candidate": 0,
                **_zero_stats_phase2(base),
            })

    # Phase 2: hit-0 のみを alternatenames でマッチング
    print("\n" + "=" * 50)
    print("Phase 2: [alternatenames] でマッチング（Phase1 の hit-0 が対象、hit-2+ は除外）")
    print("=" * 50)
    phase2_results = {}
    for i, excel_path in enumerate(excel_files):
        base = make_output_base(excel_path)
        df_phase1 = phase1_results.get(base)
        country_code = extract_country_code(excel_path)
        df_phase2, stats2 = process_one_country_phase2(
            df_phase1, base, country_code, overseas_map, db
        )
        if df_phase2 is not None:
            phase2_results[base] = df_phase2
        if i < len(all_stats):
            all_stats[i].update(stats2 if stats2 is not None else _zero_stats_phase2(base))

    # Excel 出力
    print("\n" + "=" * 50)
    print("Excel 出力")
    print("=" * 50)
    for base in phase1_results:
        _write_phase1_excel(phase1_results[base], base, OUTPUT_NAME_DIR)
    for base in phase2_results:
        _write_phase2_excel(phase2_results[base], base, OUTPUT_ALTERNATE_DIR)

    # 統計表
    stats_df = _build_tower1_stats(all_stats)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stats_path = OUTPUT_DIR / STATS_FILENAME
    stats_df.to_excel(stats_path, index=False)
    print(f"{stats_path.name} saved ({len(stats_df)} rows)")


if __name__ == "__main__":
    main()
