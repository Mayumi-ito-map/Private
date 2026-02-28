import pandas as pd
import regex
import warnings
from pathlib import Path

# =====================
# パス安全化（司令塔①から normalizers モジュールとして利用）
# =====================
BASE_DIR = Path(__file__).resolve().parent
abbreviation_file = BASE_DIR / "略語変換表.xlsx"

# =====================
# 正規表現
# =====================
dot_pattern = regex.compile(r"^(.*?)([\p{Latin}]+?\.)([^\s\-].+)$")

fjyord_suffix_pattern = regex.compile(
    r"^(?P<stem>.+?)fj\.$",
    regex.IGNORECASE
)

# =====================
# ① Excel → 辞書（valueは list）
# =====================
def load_abbreviation_dict(excel_path: Path):
    if not excel_path.exists():
        raise FileNotFoundError(f"変換表が見つかりません: {excel_path}")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        df = pd.read_excel(excel_path, engine="openpyxl")

    df = df.fillna("")

    abb_dict = {}

    for _, row in df.iterrows():
        key = str(row["略称"]).strip()
        value = str(row["フルスペル"]).strip()

        if not key or not value:
            continue

        abb_dict.setdefault(key, []).append(value)

    return abb_dict


# =====================
# ② カンマ並び替え
# =====================
def reorder_by_comma(text: str):
    if "," not in text:
        return [text]      # ← 必ず list

    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2:
        return [text]

    return [f"{parts[1]} {parts[0]}"]


# =====================
# ③ 略語展開（1 → N）
# =====================
def replace_abbreviation_with_dict(text, abbreviation_dict):
    # return [text]

    # 以下は略語展開ありの場合に使用
    results = [text]

    for key, values in abbreviation_dict.items():
        new_results = []
        for r in results:
            if key in r:
                new_results.append(r)  # ← 元を残す
                for v in values:
                    new_results.append(r.replace(key, v))
            else:
                new_results.append(r)

        results = new_results

    return list(set(results))


# =====================
# ④ fj. 展開
# =====================
def expand_fjord_suffix(text: str):
    m = fjyord_suffix_pattern.match(text)
    if not m:
        return [text]

    stem = m.group("stem")

    return [
        f"{stem}fiord",
        f"{stem}fjorden",
        f"{stem}fjörður",
    ]


# =====================
# ⑤ 正規化本体（必ず list を返す）
# =====================
def edit_place_name(text: str, abbreviation_dict):
    texts = expand_fjord_suffix(text)

    # ピリオド直後スペース補正
    fixed = []
    for t in texts:
        mo = dot_pattern.search(t)
        if mo:
            fixed.append(mo.group(1) + mo.group(2) + " " + mo.group(3))
        else:
            fixed.append(t)

    texts = fixed

    # カンマ順
    comma_reordered_texts = []
    for t in texts:
        comma_reordered_texts.extend(reorder_by_comma(t))
    texts = comma_reordered_texts

    # 略語展開（1→N）※実験で略語をそのまま使うときは以下をコメントアウト
    expanded_texts = []
    for t in texts:
        expanded_texts.extend(
            replace_abbreviation_with_dict(t, abbreviation_dict)
        )
    texts = expanded_texts

    # 重複除去＋ソート
    return sorted(set(texts))


# =====================
# モジュールロード時に1回だけ辞書読み込み
# =====================
_abbreviation_dict = load_abbreviation_dict(abbreviation_file)


def edit_comma_abb(text: str, use_abbreviation: bool = True):
    """
    外部から呼ばれる関数。
    use_abbreviation=False のときは略語展開を行わない（① Excel→辞書 を行わない場合と同等）。
    """
    abb = _abbreviation_dict if use_abbreviation else {}
    return edit_place_name(text, abb)

# =====================
# 単体テスト
# =====================
def main():
    test_place_names = [
        "B. de Seine",
        "Tel. Bay",
        "Ré,Î.de",
        "Str.of Bonifacio",
        "Breidafj.",
        "Sognefj.",
        "V. mount",
        "S. find",
    ]

    for name in test_place_names:
        results = edit_comma_abb(name)
        print(f"\n元: {name}")
        for r in results:
            print("  →", r)


if __name__ == "__main__":
    main()
