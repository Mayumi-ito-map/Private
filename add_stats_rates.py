"""
add_stats_rates.py

tower1_world_stats.xlsx を読み込み、
・候補あたりヒット率
・Phase2 解決率
・司令塔②への流出率
を追加して別名保存する。

入力: output_match/tower1_world_stats.xlsx
出力: output_match/tower1_world_stats_rates.xlsx
"""

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "output_match" / "tower1_world_stats.xlsx"
OUTPUT_PATH = BASE_DIR / "output_match" / "tower1_world_stats_rates.xlsx"


def main():
    if not INPUT_PATH.exists():
        print(f"Error: {INPUT_PATH} not found. Run run_local_build.py first.")
        return

    df = pd.read_excel(INPUT_PATH, engine="openpyxl")

    # 候補あたりヒット率(%) = (hit-name-1 + hit-name-2+_can) / total_can × 100
    hit_name_1 = df["hit-name-1"]
    hit_name_2p_can = df["hit-name-2+_can"]
    total_can = df["total_can"]
    df["候補あたりヒット率(%)"] = (
        (hit_name_1 + hit_name_2p_can) / total_can.replace(0, float("nan"))
    ).fillna(0).mul(100).round(1)

    # Phase2 解決率(%) = (hit-alter-1 + hit-alter-2+_row) / hit-name-0_row × 100
    hit_alter_1 = df["hit-alter-1"]
    hit_alter_2p_row = df["hit-alter-2+_row"]
    hit_name_0_row = df["hit-name-0_row"]
    df["Phase2解決率(%)"] = (
        (hit_alter_1 + hit_alter_2p_row) / hit_name_0_row.replace(0, float("nan"))
    ).fillna(0).mul(100).round(1)

    # 司令塔②への流出率(%) = hit-alter-0+_row / total_row × 100
    hit_alter_0_row = df["hit-alter-0+_row"]
    total_row = df["total_row"]
    df["司令塔②への流出率(%)"] = (
        hit_alter_0_row / total_row.replace(0, float("nan"))
    ).fillna(0).mul(100).round(1)

    df.to_excel(OUTPUT_PATH, index=False)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
