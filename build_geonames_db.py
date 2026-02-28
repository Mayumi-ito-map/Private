"""
build_geonames_db.py

GeoNames allCountries.txt と alternateNames.txt を
地理オブジェクトDB構造 pickle に変換するスクリプト

※ allCountries.txt の alternatenames 列は ASCII 表記のみ。
  ハングル・漢字等は alternateNames.txt に含まれるため、本スクリプトでマージする。

生成物：
- geonames_master.pkl
    {
        "by_id": {...},
        "by_cc": {...},
        "by_cc_name": {...},
        "by_cc_alternatename": {...}
    }
"""

import pickle
import unicodedata
from pathlib import Path


# ==============================
# パス設定
# ==============================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "allCountries.txt"
ALTERNATE_NAMES_FILES = [
    BASE_DIR / "alternateNames.txt",
    BASE_DIR / "alternateNamesV2.txt",
]
OUTPUT_FILE = BASE_DIR / "geonames_master.pkl"

# alternateNames でスキップする isolanguage（地名以外）
SKIP_ISOLANGUAGE = frozenset({"link", "post", "iata", "icao", "faac", "abbr", "wkdt"})


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
    by_cc = {}

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
                "cc": parts[8],
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
            cc = record["cc"]
            by_cc.setdefault(cc, []).append(geonameid)

            if i % 500000 == 0:
                print(f"{i:,} lines processed")

    # alternateNames.txt をマージ（ハングル・漢字等は allCountries に含まれないため）
    alt_file = next((f for f in ALTERNATE_NAMES_FILES if f.exists()), None)
    if alt_file:
        print(f"Reading {alt_file.name} (merge Hangul/Chinese into alternatenames)...")
        merged = 0
        skipped_lang = 0
        skipped_unknown = 0
        with open(alt_file, encoding="utf-8") as f:
            for i, line in enumerate(f):
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                gid = parts[1]
                if gid == "geonameId":  # ヘッダ行をスキップ
                    continue
                isolang = (parts[2] or "").strip().lower()
                alt_name = (parts[3] or "").strip()
                if not alt_name:
                    continue
                if isolang in SKIP_ISOLANGUAGE:
                    skipped_lang += 1
                    continue
                record = by_id.get(gid)
                if record is None:
                    skipped_unknown += 1
                    continue
                alts = record["alternatenames"]
                if alt_name not in alts:
                    alts.append(alt_name)
                    merged += 1
                if (i + 1) % 1000000 == 0:
                    print(f"  alternateNames: {i+1:,} lines, merged {merged:,}")
        print(f"  alternateNames: merged {merged:,} names into {len(by_id):,} records")
    else:
        print("  (alternateNames.txt / alternateNamesV2.txt not found - skip. Hangul/Chinese matching may not work.)")

    # -------------------
    # by_cc_name, by_cc_alternatename を構築（NFC 正規化済みキー）
    # -------------------
    print("Building by_cc_name and by_cc_alternatename ...")
    by_cc_name = {}
    by_cc_alternatename = {}

    for geonameid, record in by_id.items():
        cc = record.get("cc", "")
        if not cc:
            continue

        # name
        name = record.get("name")
        if name:
            key = unicodedata.normalize("NFC", name)
            by_cc_name.setdefault(cc, {}).setdefault(key, []).append(record)

        # alternatenames
        alts = record.get("alternatenames")
        if isinstance(alts, list):
            for alt in alts:
                if alt:
                    key = unicodedata.normalize("NFC", alt)
                    by_cc_alternatename.setdefault(cc, {}).setdefault(key, []).append(record)

        if int(geonameid or 0) % 500000 == 0 and int(geonameid or 0) > 0:
            pass  # 進捗表示は by_id の順序が不定のため省略

    print(f"  by_cc_name: {len(by_cc_name)} countries")
    print(f"  by_cc_alternatename: {len(by_cc_alternatename)} countries")

    print("Building final structure...")

    db = {
        "by_id": by_id,
        "by_cc": by_cc,
        "by_cc_name": by_cc_name,
        "by_cc_alternatename": by_cc_alternatename,
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
