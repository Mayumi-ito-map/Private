"""
run_google_api_match.py

GeoJSON の title_from_google_api（compound_code）から地名を抽出し、
GeoNames の name / alternatenames と完全一致マッチングを行う。
FCL フィルタ・距離フィルタは適用しない。

使い方:
  cd /Users/itoumayumi/Desktop/project/scripts/pipeline_merged
  python run_google_api_match.py --region cn100_europe

エリア: cn000_asia, cn100_europe, cn200_africa, cn300_america, cn450_oceania
"""

import argparse
import json
import pickle
import sys
import unicodedata
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent

PKL_PATH = BASE_DIR / "geonames_master.pkl"
GEOJSON_DIR = BASE_DIR / "geojson" / "by_region"
OUTPUT_DIR = BASE_DIR / "output_google_api_match"


# =========================================================
# GeoNames ユーティリティ（geonames_loader.py の geopandas 依存を回避）
# =========================================================

def _load_pkl() -> dict:
    if not PKL_PATH.exists():
        raise FileNotFoundError(f"{PKL_PATH} が見つかりません")
    print(f"  Loading {PKL_PATH.name} ({PKL_PATH.stat().st_size / 1e9:.1f} GB) ...",
          flush=True)
    with open(PKL_PATH, "rb") as f:
        return pickle.load(f)


def _get_records(db: dict, iso_codes: list[str]) -> list[dict]:
    by_id = db["by_id"]
    by_cc = db.get("by_ccode") or db.get("by_cc", {})
    gids = []
    for cc in iso_codes:
        gids.extend(by_cc.get(cc, []))
    gids = list(dict.fromkeys(gids))
    return [dict(by_id[g]) for g in gids if g in by_id]


def _build_dict(records: list[dict], field: str) -> dict:
    expanded: dict[str, list[dict]] = {}
    for rec in records:
        names = []
        if field == "name":
            if rec.get("name"):
                names.append(rec["name"])
        elif field == "alternatenames":
            alt = rec.get("alternatenames")
            if isinstance(alt, list):
                names.extend(alt)
            elif isinstance(alt, str) and alt:
                names.extend(a.strip() for a in alt.split(",") if a.strip())
        for n in names:
            if n:
                key = unicodedata.normalize("NFC", n)
                expanded.setdefault(key, []).append(rec)
    return expanded

REGION_MAP = {
    "cn000_asia": "cn000_asia.geojson",
    "cn100_europe": "cn100_europe.geojson",
    "cn200_africa": "cn200_africa.geojson",
    "cn300_america": "cn300_america.geojson",
    "cn450_oceania": "cn450_oceania.geojson",
}

# =========================================================
# IOC 3-letter → ISO 2-letter 国コード変換
# =========================================================
IOC_TO_ISO = {
    "AFG": "AF", "ALB": "AL", "ALG": "DZ", "AND": "AD", "ANG": "AO",
    "ANN": "NL", "ANT": "AG", "ARG": "AR", "ARM": "AM", "ARU": "AW",
    "ASM": "AS", "AUS": "AU", "AUT": "AT", "AZE": "AZ",
    "BAH": "BS", "BAN": "BD", "BAR": "BB", "BDI": "BI", "BEL": "BE",
    "BEN": "BJ", "BER": "BM", "BHU": "BT", "BIH": "BA", "BIZ": "BZ",
    "BLR": "BY", "BOL": "BO", "BOT": "BW", "BRA": "BR", "BRN": "BH",
    "BRU": "BN", "BUL": "BG", "BUR": "BF",
    "CAF": "CF", "CAM": "KH", "CAN": "CA", "CGO": "CG", "CHA": "TD",
    "CHI": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM", "COD": "CD",
    "COK": "CK", "COL": "CO", "COM": "KM", "CPV": "CV", "CRC": "CR",
    "CRO": "HR", "CUB": "CU", "CYP": "CY", "CZE": "CZ",
    "DEN": "DK", "DJI": "DJ", "DMA": "DM", "DOM": "DO",
    "ECU": "EC", "EGY": "EG", "ERI": "ER", "ESA": "SV", "ESH": "EH",
    "ESP": "ES", "EST": "EE", "ETH": "ET",
    "FIJ": "FJ", "FIN": "FI", "FLK": "FK", "FRA": "FR", "FSM": "FM",
    "GAB": "GA", "GAM": "GM", "GBR": "GB", "GEO": "GE", "GER": "DE",
    "GHA": "GH", "GLP": "GP", "GRE": "GR", "GRL": "GL", "GUA": "GT",
    "GUF": "GF", "GUI": "GN", "GUM": "GU", "GUY": "GY",
    "HAI": "HT", "HKG": "HK", "HON": "HN", "HUN": "HU",
    "INA": "ID", "IND": "IN", "IRI": "IR", "IRQ": "IQ", "ISL": "IS",
    "ISR": "IL", "ISV": "VI", "ITA": "IT",
    "JAM": "JM", "JOR": "JO", "JPN": "JP",
    "KAZ": "KZ", "KEN": "KE", "KGZ": "KG", "KIR": "KI",
    "KOR": "KR", "KOS": "XK", "KSA": "SA", "KUW": "KW",
    "LAO": "LA", "LAT": "LV", "LBA": "LY", "LBR": "LR", "LCA": "LC",
    "LES": "LS", "LIB": "LB", "LIE": "LI", "LTU": "LT", "LUX": "LU",
    "MAD": "MG", "MAS": "MY", "MAR": "MA", "MAW": "MW", "MDA": "MD",
    "MDV": "MV", "MEX": "MX", "MGL": "MN", "MKD": "MK", "MLI": "ML",
    "MLT": "MT", "MNE": "ME", "MON": "MC", "MOZ": "MZ", "MRI": "MU",
    "MTN": "MR", "MTQ": "MQ", "MYA": "MM", "MYT": "YT",
    "NAM": "NA", "NCA": "NI", "NCL": "NC", "NED": "NL", "NEP": "NP",
    "NGR": "NG", "NIG": "NE", "NOR": "NO", "NRU": "NR", "NZL": "NZ",
    "OMA": "OM",
    "PAK": "PK", "PAN": "PA", "PAR": "PY", "PER": "PE", "PHI": "PH",
    "PLE": "PS", "PLW": "PW", "PNG": "PG", "POL": "PL", "POR": "PT",
    "PRK": "KP", "PUR": "PR", "PYF": "PF",
    "QAT": "QA",
    "REU": "RE", "ROU": "RO", "RSA": "ZA", "RUS": "RU", "RWA": "RW",
    "SAM": "WS", "SEN": "SN", "SEY": "SC", "SHN": "SH", "SIN": "SG",
    "SKN": "KN", "SLE": "SL", "SLO": "SI", "SMR": "SM", "SOL": "SB",
    "SOM": "SO", "SPM": "PM", "SRB": "RS", "SRI": "LK", "SSD": "SS",
    "STP": "ST", "SUD": "SD", "SUI": "CH", "SUR": "SR", "SVK": "SK",
    "SWE": "SE", "SWZ": "SZ", "SYR": "SY",
    "TAN": "TZ", "TGA": "TO", "THA": "TH", "TJK": "TJ", "TKM": "TM",
    "TLS": "TL", "TOG": "TG", "TPE": "TW", "TTO": "TT", "TUN": "TN",
    "TUR": "TR", "TUV": "TV",
    "UAE": "AE", "UGA": "UG", "UKR": "UA", "URU": "UY", "USA": "US",
    "UZB": "UZ",
    "VAN": "VU", "VEN": "VE", "VIE": "VN", "VIN": "VC",
    "WLF": "WF",
    "YEM": "YE",
    "ZAM": "ZM", "ZIM": "ZW",
    "ANTARC": "AQ",
}


# =========================================================
# 地名抽出
# =========================================================

def _extract_place_name(title) -> tuple[str | None, str]:
    """
    title_from_google_api から地名と形式タイプを返す。
    compound_code 形式のみ抽出可能。文字列（住所）形式は Phase2 で対応予定。
    """
    if title is None:
        return None, "none"
    if isinstance(title, dict):
        cc = title.get("compound_code")
        if cc:
            parts = str(cc).split(" ", 1)
            if len(parts) == 2 and parts[1].strip():
                location = parts[1]
                name_parts = [p.strip() for p in location.split(",")]
                if name_parts and name_parts[0]:
                    return name_parts[0], "compound_code"
            return None, "compound_parse_error"
        return None, "global_code_only"
    if isinstance(title, str):
        return None, "address_string"
    return None, "unknown"


def _ioc_to_iso_codes(ioc_country: str) -> list[str]:
    """IOC 3-letter コードを ISO 2-letter に変換。複合コード（／区切り）にも対応。"""
    if not ioc_country or pd.isna(ioc_country):
        return []
    result = []
    for part in str(ioc_country).replace("/", "／").split("／"):
        part = part.strip().split(",")[0].strip()
        if not part:
            continue
        iso = IOC_TO_ISO.get(part)
        if iso:
            result.append(iso)
    return list(dict.fromkeys(result))


# =========================================================
# マッチング
# =========================================================

def _match_one(place_name: str, name_dict: dict, alt_dict: dict) -> dict:
    """1 地名 → GeoNames name / alternatenames で完全一致。"""
    key = unicodedata.normalize("NFC", place_name)

    for field, d, prefix in [("name", name_dict, "hit-name"), ("alter", alt_dict, "hit-alter")]:
        hits = d.get(key, [])
        if hits:
            n = len(hits)
            judge = "1" if n == 1 else "2+"
            _s = lambda v: "" if v is None else str(v)
            return {
                "ga_judge": judge,
                "ga_matched_stage": f"{prefix}-{judge}",
                "ga_matched": True,
                "ga_hit_count": n,
                "ga_matched_geonameid": " | ".join(_s(h.get("geonameid")) for h in hits),
                "ga_matched_fcl": " | ".join(_s(h.get("fcl")) for h in hits),
                "ga_matched_fcode": " | ".join(_s(h.get("fcode")) for h in hits),
                "ga_matched_gn_name": " | ".join(_s(h.get("name")) for h in hits),
                "ga_matched_ccode": " | ".join(_s(h.get("ccode")) for h in hits),
            }

    return {
        "ga_judge": "0",
        "ga_matched_stage": "",
        "ga_matched": False,
        "ga_hit_count": 0,
        "ga_matched_geonameid": "",
        "ga_matched_fcl": "",
        "ga_matched_fcode": "",
        "ga_matched_gn_name": "",
        "ga_matched_ccode": "",
    }


_EMPTY_RESULT = {
    "ga_judge": "",
    "ga_matched_stage": "",
    "ga_matched": "",
    "ga_hit_count": "",
    "ga_matched_geonameid": "",
    "ga_matched_fcl": "",
    "ga_matched_fcode": "",
    "ga_matched_gn_name": "",
    "ga_matched_ccode": "",
}


# =========================================================
# 比較
# =========================================================

def _comparison_label(existing_flag, ga_matched) -> str:
    """既存マッチングとの比較ラベルを返す。"""
    existing = str(existing_flag).strip() if pd.notna(existing_flag) else ""
    if ga_matched is True:
        if existing == "×":
            return "★new_match"
        if existing == "T":
            return "confirmed"
        return "ga_only"
    else:
        if existing == "T":
            return "existing_only"
        if existing == "×":
            return "both_zero"
        return ""


# =========================================================
# メイン処理
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description="GeoJSON title_from_google_api → GeoNames 完全一致マッチング"
    )
    parser.add_argument(
        "--region", required=True,
        choices=list(REGION_MAP.keys()),
        help="対象エリア",
    )
    args = parser.parse_args()

    region = args.region
    geojson_path = GEOJSON_DIR / REGION_MAP[region]
    if not geojson_path.exists():
        print(f"Error: {geojson_path} が見つかりません")
        return

    # ── 1. GeoJSON 読み込み ──
    print(f"Loading {geojson_path.name} ...", flush=True)
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    features = gj["features"]
    print(f"  {len(features):,} features", flush=True)

    # ── 2. 地名抽出 ──
    print("Extracting place names ...", flush=True)
    rows = []
    for feat in features:
        props = feat.get("properties", {})
        title = props.get("title_from_google_api")
        place_name, source_type = _extract_place_name(title)
        rows.append({
            "index_id": props.get("index_id"),
            "english_title": props.get("english_title"),
            "country": props.get("country"),
            "lo_fcl": props.get("category"),
            "existing_matched_flag": props.get("matched_flag"),
            "google_api_name": place_name,
            "source_type": source_type,
        })
    df = pd.DataFrame(rows)

    src_counts = df["source_type"].value_counts()
    print("  source_type:", flush=True)
    for st, cnt in src_counts.items():
        print(f"    {st}: {cnt:,}", flush=True)
    extractable = df["google_api_name"].notna().sum()
    print(f"  抽出可能: {extractable:,} / {len(df):,}", flush=True)

    # ── 3. GeoNames 読み込み ──
    print("\nLoading geonames_master.pkl ...", flush=True)
    db = _load_pkl()
    print("  done.", flush=True)

    # ── 4. 国ごとにマッチング（メモリ効率重視） ──
    print("Matching (country by country) ...\n", flush=True)

    ga_cols = list(_EMPTY_RESULT.keys())
    for col in ga_cols:
        df[col] = None

    ioc_groups = df.groupby("country", sort=False)
    n_countries = 0
    n_matched_total = 0

    for ioc_code, grp in ioc_groups:
        iso_codes = _ioc_to_iso_codes(ioc_code)
        if not iso_codes:
            continue

        records = _get_records(db, iso_codes)
        if not records:
            continue

        name_dict = _build_dict(records, field="name")
        alt_dict = _build_dict(records, field="alternatenames")
        n_countries += 1
        n_matched_country = 0

        for idx in grp.index:
            pname = df.at[idx, "google_api_name"]
            if pd.isna(pname) or not pname:
                for col in ga_cols:
                    df.at[idx, col] = _EMPTY_RESULT[col]
                continue
            result = _match_one(pname, name_dict, alt_dict)
            for col in ga_cols:
                df.at[idx, col] = result[col]
            if result["ga_matched"] is True:
                n_matched_country += 1

        n_with_name = grp["google_api_name"].notna().sum()
        if n_with_name > 0:
            print(f"  {ioc_code}: {n_matched_country}/{n_with_name} matched "
                  f"({len(records):,} geonames records)", flush=True)
        n_matched_total += n_matched_country

    print(f"\n  合計: {n_countries} countries, {n_matched_total} matched", flush=True)

    # ── 5. 比較列 ──
    df["comparison"] = df.apply(
        lambda r: _comparison_label(r["existing_matched_flag"], r["ga_matched"])
        if r["google_api_name"] and pd.notna(r["google_api_name"])
        else "no_google_data",
        axis=1,
    )

    # ── 6. 統計 ──
    print("\n=== 統計 ===")
    total = len(df)
    has_name = int(df["google_api_name"].notna().sum())
    df_with_name = df[df["google_api_name"].notna()]
    ga_hit = int((df_with_name["ga_matched"] == True).sum())
    ga_zero = int((df_with_name["ga_judge"] == "0").sum())

    print(f"  全件数: {total:,}")
    print(f"  地名抽出可能 (compound_code): {has_name:,}")
    print(f"  GeoNames マッチ: {ga_hit:,}  |  0マッチ: {ga_zero:,}")

    comp_counts = df["comparison"].value_counts()
    print("\n  比較結果:")
    for label in ["★new_match", "confirmed", "existing_only", "both_zero",
                   "ga_only", "no_google_data"]:
        cnt = int(comp_counts.get(label, 0))
        if cnt > 0:
            print(f"    {label}: {cnt:,}")

    # ── 7. Excel 出力 ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{region}_google_api_match.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all", index=False)

        df_new = df[df["comparison"] == "★new_match"]
        if len(df_new) > 0:
            df_new.to_excel(writer, sheet_name="new_match", index=False)

        df_conf = df[df["comparison"] == "confirmed"]
        if len(df_conf) > 0:
            df_conf.to_excel(writer, sheet_name="confirmed", index=False)

        df_both0 = df[df["comparison"] == "both_zero"]
        if len(df_both0) > 0:
            df_both0.to_excel(writer, sheet_name="both_zero", index=False)

        stats_rows = [
            ("全件数", total),
            ("", ""),
            ("--- source_type ---", ""),
            ("compound_code（抽出可能）", has_name),
            ("address_string（未対応）", int(src_counts.get("address_string", 0))),
            ("global_code_only（抽出不可）", int(src_counts.get("global_code_only", 0))),
            ("none（データなし）", int(src_counts.get("none", 0))),
            ("", ""),
            ("--- マッチング結果 ---", ""),
            ("GeoNames マッチ", ga_hit),
            ("  hit-name-1", int((df["ga_matched_stage"] == "hit-name-1").sum())),
            ("  hit-name-2+", int((df["ga_matched_stage"] == "hit-name-2+").sum())),
            ("  hit-alter-1", int((df["ga_matched_stage"] == "hit-alter-1").sum())),
            ("  hit-alter-2+", int((df["ga_matched_stage"] == "hit-alter-2+").sum())),
            ("0マッチ", ga_zero),
            ("", ""),
            ("--- 既存結果との比較 ---", ""),
            ("★new_match（既存×→GA○）", int(comp_counts.get("★new_match", 0))),
            ("confirmed（既存○→GA○）", int(comp_counts.get("confirmed", 0))),
            ("existing_only（既存○→GA×）", int(comp_counts.get("existing_only", 0))),
            ("both_zero（既存×→GA×）", int(comp_counts.get("both_zero", 0))),
            ("no_google_data（抽出不可）", int(comp_counts.get("no_google_data", 0))),
        ]
        pd.DataFrame(stats_rows, columns=["項目", "件数"]).to_excel(
            writer, sheet_name="summary", index=False
        )

    print(f"\n出力: {out_path}", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
