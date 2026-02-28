"""
calc_distance.py

output_match_name/*_name.xlsx と output_match_alternatenames/*_alternate.xlsx を読み込み、
hit-1 の行について local_lat, local_lon と matched_lat, matched_lon の距離（km）を計算し、
distance 列に反映して上書き保存する。

入力: output_match_name/*_name.xlsx, output_match_alternatenames/*_alternate.xlsx
出力: 上書き保存
"""

import math
import warnings
from pathlib import Path

import pandas as pd

from utils import is_excel_lock_file

BASE_DIR = Path(__file__).resolve().parent
INPUT_NAME_DIR = BASE_DIR / "output_match_name"
INPUT_ALTERNATE_DIR = BASE_DIR / "output_match_alternatenames"

REQUIRED_COLS = ["local_lat", "local_lon", "matched_lat", "matched_lon"]
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    2点間の大圏距離（km）を Haversine 式で計算。
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def calc_distance_row(row) -> float | None:
    """1行の4列から距離を計算。欠損があれば None。"""
    try:
        lat1 = float(row["local_lat"])
        lon1 = float(row["local_lon"])
        lat2 = float(row["matched_lat"])
        lon2 = float(row["matched_lon"])
    except (TypeError, ValueError):
        return None
    if math.isnan(lat1) or math.isnan(lon1) or math.isnan(lat2) or math.isnan(lon2):
        return None
    return round(haversine_km(lat1, lon1, lat2, lon2), 2)


def process_file(path: Path, judge_col: str, judge_val: str) -> int:
    """
    1ファイルを処理。hit-1 の行に距離を計算し、distance 列を更新して上書き保存。
    返値: 距離を計算した行数
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df = pd.read_excel(path, engine="openpyxl")

    for col in REQUIRED_COLS:
        if col not in df.columns:
            print(f"  skip {path.name}: missing column {col}")
            return 0

    if judge_col not in df.columns:
        print(f"  skip {path.name}: missing column {judge_col}")
        return 0

    if "distance" not in df.columns:
        df["distance"] = None

    mask = df[judge_col] == judge_val
    hit1_rows = df.loc[mask]

    if len(hit1_rows) == 0:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
            df.to_excel(path, index=False, engine="openpyxl")
        return 0

    count = 0
    for idx in hit1_rows.index:
        d = calc_distance_row(df.loc[idx])
        if d is not None:
            df.at[idx, "distance"] = d
            count += 1

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df.to_excel(path, index=False)

    return count


def main():
    name_files = sorted(INPUT_NAME_DIR.glob("cn*_name.xlsx"))
    name_files = [p for p in name_files if not is_excel_lock_file(p)]

    alt_files = sorted(INPUT_ALTERNATE_DIR.glob("cn*_alternate.xlsx"))
    alt_files = [p for p in alt_files if not is_excel_lock_file(p)]

    total_name = 0
    total_alt = 0

    print("=== *_name.xlsx (hit-name-1) ===")
    for path in name_files:
        n = process_file(path, judge_col="name_judge", judge_val="1")
        total_name += n
        if n > 0:
            print(f"  {path.name}: {n} rows")

    print("\n=== *_alternate.xlsx (hit-alter-1) ===")
    for path in alt_files:
        n = process_file(path, judge_col="alter_judge", judge_val="1")
        total_alt += n
        if n > 0:
            print(f"  {path.name}: {n} rows")

    print(f"\nDone. name: {total_name} distances, alternate: {total_alt} distances")


if __name__ == "__main__":
    main()
