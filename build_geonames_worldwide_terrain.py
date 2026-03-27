"""
build_geonames_worldwide_terrain.py

geonames_master.pkl から fcl ∈ {T, H, U, V} のレコードのみを抽出し、
全世界マッチング用の軽量 pkl を生成する。

出力: geonames_worldwide_terrain.pkl
  - records: list[dict]  fcl が T/H/U/V の全レコード
  - 海・山・海底地形など、国境をまたぐ地名の全世界マッチング用

参照: memo/260304/全世界マッチング_海山地名_検討報告書.md
"""

import pickle
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_PKL = BASE_DIR / "geonames_master.pkl"
OUTPUT_PKL = BASE_DIR / "geonames_worldwide_terrain.pkl"

GN_FCL_WORLDWIDE = ("T", "H", "U", "V")


def build_worldwide_terrain_pkl():
    """geonames_master.pkl から fcl ∈ {T,H,U,V} のレコードを抽出し保存。"""
    if not INPUT_PKL.exists():
        raise FileNotFoundError(f"{INPUT_PKL} が見つかりません。先に build_geonames_db.py を実行してください。")

    print(f"Loading {INPUT_PKL.name} ...")
    with open(INPUT_PKL, "rb") as f:
        db = pickle.load(f)
    by_id = db["by_id"]

    print(f"Filtering fcl ∈ {GN_FCL_WORLDWIDE} ...")
    records = []
    for geonameid, record in by_id.items():
        fcl = record.get("fcl", "")
        if fcl in GN_FCL_WORLDWIDE:
            records.append(dict(record))

    print(f"  {len(records):,} records")

    print(f"Saving {OUTPUT_PKL.name} ...")
    with open(OUTPUT_PKL, "wb") as f:
        pickle.dump({"records": records}, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("Done.")
    print(f"Output: {OUTPUT_PKL}")


if __name__ == "__main__":
    build_worldwide_terrain_pkl()
