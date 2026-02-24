"""
build_geonames_db.py

GeoNames allCountries.txt を
地理オブジェクトDB構造 pickle に変換するスクリプト

生成物：
- geonames_master.pkl
    {
        "by_id": {...},
        "by_ccode": {...},
        "by_fcl": {...},
        "by_fcode": {...}
    }
"""

import pickle
from pathlib import Path


# ==============================
# パス設定
# ==============================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "allCountries.txt"
OUTPUT_FILE = BASE_DIR / "geonames_master.pkl"


# ==============================
# ユーティリティ
# ==============================

def safe_int(value):
    try:
        return int(value)
    except:
        return None


def safe_float(value):
    try:
        return float(value)
    except:
        return None


def split_alternatenames(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


# ==============================
# メイン処理
# ==============================

def build_database():

    by_id = {}
    by_ccode = {}
    by_fcl = {}
    by_fcode = {}

    print("Reading allCountries.txt ...")

    with open(INPUT_FILE, encoding="utf-8") as f:

        for i, line in enumerate(f):

            parts = line.rstrip("\n").split("\t")

            if len(parts) < 19:
                continue

            geonameid = parts[0]

            record = {
                "geonameid": geonameid,
                "name": parts[1],
                "asciiname": parts[2],
                "alternatenames": split_alternatenames(parts[3]),
                "lat": safe_float(parts[4]),
                "lon": safe_float(parts[5]),
                "fcl": parts[6],
                "fcode": parts[7],
                "ccode": parts[8],
                "cc2": parts[9],
                "ad1": parts[10],
                "ad2": parts[11],
                "ad3": parts[12],
                "ad4": parts[13],
                "population": safe_int(parts[14]),
                "elevation": safe_int(parts[15]),
                "dem": safe_int(parts[16]),
                "timezone": parts[17],
                "mdate": parts[18],
            }

            # -------------------
            # 主キー登録
            # -------------------
            by_id[geonameid] = record

            # -------------------
            # 副インデックス
            # -------------------

            ccode = record["ccode"]
            fcl = record["fcl"]
            fcode = record["fcode"]

            by_ccode.setdefault(ccode, []).append(geonameid)
            by_fcl.setdefault(fcl, []).append(geonameid)
            by_fcode.setdefault(fcode, []).append(geonameid)

            if i % 500000 == 0:
                print(f"{i:,} lines processed")

    print("Building final structure...")

    db = {
        "by_id": by_id,
        "by_ccode": by_ccode,
        "by_fcl": by_fcl,
        "by_fcode": by_fcode,
    }

    print("Saving pickle ...")

    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(db, f, protocol=pickle.HIGHEST_PROTOCOL)

    print("Done.")
    print(f"Output: {OUTPUT_FILE}")


# ==============================
# 実行
# ==============================

if __name__ == "__main__":
    build_database()
