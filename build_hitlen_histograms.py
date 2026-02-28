"""
build_hitlen_histograms.py

output_match_name/*_name.xlsx と output_match_alternatenames/*_alternate.xlsx から、
国毎に hit_name_len / hit_alter_len のヒストグラムを作成する。
name と alternatenames の両方の傾向を比較できる。

入力: output_match_name/*_name.xlsx, output_match_alternatenames/*_alternate.xlsx
出力: output_match/histograms/*.png

オプション:
  --country FR  : 指定した文字列を含む国のみ処理（例: フランスは FR）
  省略時は全193国を処理
"""

import argparse
from pathlib import Path

import numpy as np

from utils import is_excel_lock_file
import matplotlib
matplotlib.use("Agg")  # ヘッドレス環境対応
import matplotlib.pyplot as plt
import pandas as pd

# matplotlib 3.9 + numpy 1.26 互換性: figure facecolor を明示（__array__ エラー回避）
plt.rcParams["figure.facecolor"] = "white"

# 日本語表示用フォント（macOS では Hiragino が標準搭載）
# フォント未検出時は軸ラベルが英語表示になる

BASE_DIR = Path(__file__).resolve().parent
INPUT_NAME_DIR = BASE_DIR / "output_match_name"
INPUT_ALTERNATE_DIR = BASE_DIR / "output_match_alternatenames"
OUTPUT_DIR = BASE_DIR / "output_match" / "histograms"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_base_from_name_path(path: Path) -> str:
    """cn002_AZ_アゼルバイジャン_name.xlsx → cn002_AZ_アゼルバイジャン"""
    stem = path.stem
    if stem.endswith("_name"):
        return stem[:-5]  # remove "_name"
    return stem


def get_base_from_alternate_path(path: Path) -> str:
    """cn002_AZ_アゼルバイジャン_alternate.xlsx → cn002_AZ_アゼルバイジャン"""
    stem = path.stem
    if stem.endswith("_alternate"):
        return stem[:-10]  # remove "_alternate"
    return stem


def count_hitlen(df: pd.DataFrame, col: str = "hit_len") -> dict[int, int]:
    """指定列の度数分布を返す。キー・値は Python の int に変換（matplotlib 互換）。"""
    if col not in df.columns:
        return {}
    counts = df[col].value_counts().sort_index()
    return {int(k): int(v) for k, v in counts.to_dict().items()}


def plot_histogram(
    name_counts: dict[int, int],
    alternate_counts: dict[int, int],
    country_label: str,
    out_path: Path,
):
    """
    name と alternatenames の hit 数分布を並べて棒グラフで描画。
    """
    all_keys = sorted(set(name_counts.keys()) | set(alternate_counts.keys()))
    if not all_keys:
        return

    # 10以上は「10+」にまとめる（可読性のため）
    max_display = 10
    name_bars = []
    alt_bars = []
    labels = []

    for k in all_keys:
        if k < max_display:
            labels.append(str(k))
            name_bars.append(int(name_counts.get(k, 0)))
            alt_bars.append(int(alternate_counts.get(k, 0)))

    # 10以上がある場合
    if any(k >= max_display for k in all_keys):
        name_5plus = sum(int(name_counts.get(k, 0)) for k in all_keys if k >= max_display)
        alt_5plus = sum(int(alternate_counts.get(k, 0)) for k in all_keys if k >= max_display)
        if name_5plus > 0 or alt_5plus > 0:
            labels.append(f"{max_display}+")
            name_bars.append(name_5plus)
            alt_bars.append(alt_5plus)

    x = np.arange(len(labels), dtype=np.float64)
    width = 0.35

    # 互換性のため、Python の list に変換してから numpy 配列化（matplotlib/numpy の __array__ エラー回避）
    heights1 = np.array([float(v) for v in name_bars], dtype=np.float64)
    heights2 = np.array([float(v) for v in alt_bars], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="white")
    fig.patch.set_facecolor("white")
    bars1 = ax.bar(x - width / 2, heights1, width, label="name", color="#1f77b4")
    bars2 = ax.bar(x + width / 2, heights2, width, label="alternatenames", color="#ff7f0e")

    ax.set_xlabel("hit count")
    ax.set_ylabel("count")
    ax.set_title(f"hit_name_len / hit_alter_len: {country_label}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    # 棒の上に数値を表示（0でない場合）
    for bar in bars1:
        h = float(bar.get_height())
        if h > 0:
            ax.annotate(
                f"{int(h)}",
                xy=(float(bar.get_x() + bar.get_width() / 2), h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#1f77b4",
            )
    for bar in bars2:
        h = float(bar.get_height())
        if h > 0:
            ax.annotate(
                f"{int(h)}",
                xy=(float(bar.get_x() + bar.get_width() / 2), h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#ff7f0e",
            )

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="hit_name_len / hit_alter_len ヒストグラムを国毎に生成")
    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="指定した文字列を含む国のみ処理（例: FR でフランスのみ）。省略時は全国",
    )
    args = parser.parse_args()

    name_files = sorted(INPUT_NAME_DIR.glob("cn*_name.xlsx"))
    name_files = [p for p in name_files if not is_excel_lock_file(p)]

    if args.country:
        name_files = [p for p in name_files if args.country in get_base_from_name_path(p)]
        print(f"Filter: --country {args.country} → {len(name_files)} file(s)")

    if not name_files:
        print(f"No *_name.xlsx files in {INPUT_NAME_DIR}" + (f" (filter: {args.country})" if args.country else ""))
        return

    print(f"Processing {len(name_files)} name file(s)")

    for name_path in name_files:
        base = get_base_from_name_path(name_path)
        country_label = base

        try:
            df_name = pd.read_excel(name_path, engine="openpyxl")
        except Exception as e:
            print(f" skip {name_path.name}: {e}")
            continue

        name_counts = count_hitlen(df_name, col="hit_name_len")

        alternate_path = INPUT_ALTERNATE_DIR / f"{base}_alternate.xlsx"
        if alternate_path.exists():
            try:
                df_alt = pd.read_excel(alternate_path, engine="openpyxl")
                alternate_counts = count_hitlen(df_alt, col="hit_alter_len")
            except Exception as e:
                print(f" skip alternate {alternate_path.name}: {e}")
                alternate_counts = {}
        else:
            alternate_counts = {}

        if not name_counts and not alternate_counts:
            print(f" skip {base}: no hit_name_len / hit_alter_len data")
            continue

        out_path = OUTPUT_DIR / f"{base}.png"
        plot_histogram(name_counts, alternate_counts, country_label, out_path)
        print(f" wrote {out_path}")

    print(f"\nHistograms saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

