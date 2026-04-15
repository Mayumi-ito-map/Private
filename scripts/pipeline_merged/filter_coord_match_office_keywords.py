"""
coord_match 出力から「役所」系ローマ字を含む候補だけを抽出し、go_coord_* 列を付与する。

入力: output_match_coord/*_coord_match.xlsx（シート all を既定で使用）
判定: coord_matched_name を「 | 」分割した各候補に対し、キーワードのいずれかが部分一致すれば採用
出力: 同一ディレクトリに *_office.xlsx（マッチなしの行は go_coord_* は空欄）

続けて go_coord_* を「 | 」分割した先頭要素だけを
go_name, go_km, go_geonameid, go_fcl, go_fcode, go_go_lat, go_go_lon に格納する
（既存の Google 役所 go_lat/go_lon とは別名で衝突しない）。

*_office.xlsx を入力にした場合は役所フィルタをスキップし、先頭列の付与のみ行う。
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import warnings
from pathlib import Path


import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_DIR = PROJECT_ROOT
INPUT_DIR = BASE_DIR / "output_match_coord"
OUTPUT_DIR = BASE_DIR / "output_match_coord"

# 処理対象ファイル（run_local_build / run_coord_match と同様にリストで切り替え）
MERGED_PATTERNS = [
    "cn001_JP_日本_go_coord_match.xlsx",
]

# coord_matched_name に含まれる「役所」相当（大文字小文字は casefold で無視。Ō / o 両方を列挙）
OFFICE_KEYWORDS = [
    "Tokyo Prefecture",
    "Shiyakusyo",
    "shiyakusho",
    "-shiyakusho",
    "Chōyakuba",
    "chōyakuba",
    "-chōyakuba",
    "Choyakuba",
    "choyakuba",
    "-choyakuba",
    "Machiyakuba",
    "machiyakuba",
    "-machiyakuba",
    "Murayakuba",
    "murayakuba",
    "-murayakuba",
    "City Hall",
]

SOURCE_COLS = [
    "coord_distance_km",
    "coord_matched_geonameid",
    "coord_matched_name",
    "coord_matched_fcl",
    "coord_matched_fcode",
    "coord_matched_lat",
    "coord_matched_lon",
]

OUTPUT_COLS = [
    "go_coord_distance_km",
    "go_coord_matched_geonameid",
    "go_coord_matched_name",
    "go_coord_matched_fcl",
    "go_coord_matched_fcode",
    "go_coord_matched_lat",
    "go_coord_matched_lon",
]

# go_coord_* の先頭セグメント（Google の go_lat/go_lon と区別するため緯度経度は go_go_*）
FIRST_GO_COLUMN_MAP: list[tuple[str, str]] = [
    ("go_coord_matched_name", "go_name"),
    ("go_coord_distance_km", "go_km"),
    ("go_coord_matched_geonameid", "go_geonameid"),
    ("go_coord_matched_fcl", "go_fcl"),
    ("go_coord_matched_fcode", "go_fcode"),
    ("go_coord_matched_lat", "go_go_lat"),
    ("go_coord_matched_lon", "go_go_lon"),
]

FIRST_GO_OUTPUT = [dst for _, dst in FIRST_GO_COLUMN_MAP]

PIPE_SEP = " | "


def _split_pipe_cell_strict(val) -> list[str]:
    """run_coord_match 出力と同じ「 | 」区切り。"""
    if pd.isna(val) or val == "":
        return []
    s = str(val).replace(",", "")
    return [p.strip() for p in s.split(PIPE_SEP)]


def _first_pipe_segment(val) -> str:
    parts = _split_pipe_cell_strict(val)
    return parts[0] if parts else ""


def _pad_to_length(parts: list[str], n: int) -> list[str]:
    if len(parts) >= n:
        return parts[:n]
    return parts + [""] * (n - len(parts))


def _normalized_casefold(s: str) -> str:
    return unicodedata.normalize("NFC", s).casefold()


def _name_matches_office(name: str) -> bool:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return False
    t = str(name).strip()
    if not t:
        return False
    hay = _normalized_casefold(t)
    for kw in OFFICE_KEYWORDS:
        needle = _normalized_casefold(kw)
        if needle in hay:
            return True
    return False


def _filter_row_office(row: pd.Series) -> dict[str, str]:
    names = _split_pipe_cell_strict(row.get("coord_matched_name", ""))
    n = len(names)
    if n == 0:
        return {c: "" for c in OUTPUT_COLS}

    dists = _pad_to_length(_split_pipe_cell_strict(row.get("coord_distance_km", "")), n)
    geoids = _pad_to_length(_split_pipe_cell_strict(row.get("coord_matched_geonameid", "")), n)
    fcls = _pad_to_length(_split_pipe_cell_strict(row.get("coord_matched_fcl", "")), n)
    fcodes = _pad_to_length(_split_pipe_cell_strict(row.get("coord_matched_fcode", "")), n)
    lats = _pad_to_length(_split_pipe_cell_strict(row.get("coord_matched_lat", "")), n)
    lons = _pad_to_length(_split_pipe_cell_strict(row.get("coord_matched_lon", "")), n)

    md, mg, mn, mf, mfc, mla, mlo = [], [], [], [], [], [], []
    for i in range(n):
        if _name_matches_office(names[i]):
            md.append(dists[i] if i < len(dists) else "")
            mg.append(geoids[i] if i < len(geoids) else "")
            mn.append(names[i])
            mf.append(fcls[i] if i < len(fcls) else "")
            mfc.append(fcodes[i] if i < len(fcodes) else "")
            mla.append(lats[i] if i < len(lats) else "")
            mlo.append(lons[i] if i < len(lons) else "")

    if not mn:
        return {c: "" for c in OUTPUT_COLS}

    def _join(xs: list[str]) -> str:
        return PIPE_SEP.join(xs)

    return {
        "go_coord_distance_km": _join(md),
        "go_coord_matched_geonameid": _join(mg),
        "go_coord_matched_name": _join(mn),
        "go_coord_matched_fcl": _join(mf),
        "go_coord_matched_fcode": _join(mfc),
        "go_coord_matched_lat": _join(mla),
        "go_coord_matched_lon": _join(mlo),
    }


def _reorder_go_columns(df: pd.DataFrame) -> pd.DataFrame:
    """go_coord_* と go_name 等を coord_matched_lon の直後に置く（列があれば）。"""
    anchor = "coord_matched_lon"
    tail_block = OUTPUT_COLS + FIRST_GO_OUTPUT
    cols = [c for c in df.columns if c not in tail_block]
    if anchor in cols:
        i = cols.index(anchor) + 1
        new_order = cols[:i] + tail_block + cols[i:]
    else:
        new_order = cols + tail_block
    seen = set()
    ordered = []
    for c in new_order:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return df[[c for c in ordered if c in df.columns]]


def _append_first_go_columns(df: pd.DataFrame) -> pd.DataFrame:
    for src, dst in FIRST_GO_COLUMN_MAP:
        if src not in df.columns:
            df[dst] = ""
        else:
            df[dst] = df[src].apply(_first_pipe_segment)
    return df


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "coord_matched_name" in df.columns:
        missing = [c for c in ["coord_matched_name"] + SOURCE_COLS if c not in df.columns]
        if "coord_matched_name" in missing:
            raise ValueError(f"必須列がありません: {missing}")

        for c in missing:
            if c != "coord_matched_name":
                df[c] = ""

        added = df.apply(lambda r: pd.Series(_filter_row_office(r)), axis=1)
        df_out = pd.concat([df, added], axis=1)
    else:
        missing_go = [c for c in OUTPUT_COLS if c not in df.columns]
        if missing_go:
            raise ValueError(
                "coord_matched_name がありません。役所フィルタ済み *_office.xlsx を使う場合は "
                f"go_coord_* 列が必要です。不足: {missing_go}"
            )
        df_out = df

    df_out = _append_first_go_columns(df_out)
    return _reorder_go_columns(df_out)


def _pick_sheet(path: Path, sheet: str | None) -> str:
    xl = pd.ExcelFile(path)
    if sheet and sheet in xl.sheet_names:
        return sheet
    if "all" in xl.sheet_names:
        return "all"
    return xl.sheet_names[0]


def _output_path_for(input_path: Path, out_dir: Path) -> Path:
    """coord_match → *_office.xlsx。既に *_office の入力は同じファイル名で上書き（先頭列だけ追加）。"""
    if input_path.stem.endswith("_office"):
        return out_dir / f"{input_path.stem}.xlsx"
    return out_dir / f"{input_path.stem}_office.xlsx"


def run_one_file(path: Path, sheet: str | None, out_dir: Path) -> None:
    sh = _pick_sheet(path, sheet)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df = pd.read_excel(path, sheet_name=sh)

    df_out = process_dataframe(df)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _output_path_for(path, out_dir)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name="all", index=False)

    if "go_coord_matched_name" in df_out.columns:
        nonempty = (df_out["go_coord_matched_name"].astype(str).str.len() > 0).sum()
        print(f"  sheet={sh} rows={len(df_out)} go_coord 非空行={int(nonempty)}")
    else:
        print(f"  sheet={sh} rows={len(df_out)}")
    print(f"  -> {out_path.name}")


def main():
    parser = argparse.ArgumentParser(
        description="coord_match → go_coord_* → 先頭セグメントを go_name / go_km / … / go_go_lat / go_go_lon に格納"
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help='読み込みシート名（省略時は "all"、なければ先頭シート）',
    )
    args = parser.parse_args()

    merged_files = [INPUT_DIR / p for p in MERGED_PATTERNS if (INPUT_DIR / p).exists()]
    if not merged_files:
        print(f"入力が見つかりません: {INPUT_DIR}")
        print(f"  期待: {MERGED_PATTERNS}")
        return

    print(f"入力: {INPUT_DIR}")
    print(f"対象: {[p.name for p in merged_files]}\n")

    for path in merged_files:
        print(f"=== {path.name} ===")
        run_one_file(path, args.sheet, OUTPUT_DIR)

    print("\nDone.")


if __name__ == "__main__":
    main()
