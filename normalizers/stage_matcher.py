"""
stage_matcher.py（normalizers）

段階的正規化エンジン（Stage1 / Stage2 / Stage3）
司令塔②で使用。文字列の正規化のみを担当し、マッチング制御は司令塔側で行う。
"""

import re
import unicodedata


# =========================================================
# Stage 1 : 基本正規化（形をほぼ保つ）
# =========================================================
def normalize_stage1(text: str) -> str:
    """
    基本整形：前後空白除去、全角スペース→半角、連続空白を1つに統一。
    見た目の揺れのみを吸収する。
    """
    if not text:
        return ""
    text = str(text).strip()
    text = text.replace("　", " ")
    text = re.sub(r"\s+", " ", text)
    return text


# =========================================================
# Stage 2 内部処理部品
# =========================================================

def _remove_ayn(text: str) -> str:
    """アイン系記号の除去（中東系地名の表記ゆれ対策）"""
    ayn_chars = [
        "\u02BB", "\u02BF", "\u2018", "\u2019", "\u02BC", "\u02C1",
    ]
    for ch in ayn_chars:
        text = text.replace(ch, "")
    return text


_SPECIAL_LATIN_MAP = str.maketrans({
    # --- 第1弾: AZE 調査で追加（2026-03-26） ---
    "\u0131": "i",   # ı  ドットなし i（トルコ語・アゼルバイジャン語）
    "\u0130": "I",   # İ  ドット付き I
    "\u0259": "a",   # ə  シュワー（アゼルバイジャン語）
    "\u018F": "A",   # Ə  シュワー大文字
    "\u00F0": "d",   # ð  エズ（アイスランド語）
    "\u00D0": "D",   # Ð  エズ大文字
    "\u0111": "d",   # đ  クロスド d（ベトナム語等）
    "\u0110": "D",   # Đ  クロスド D
    "\u0142": "l",   # ł  ストローク l（ポーランド語）
    "\u0141": "L",   # Ł  ストローク L
    "\u00F8": "o",   # ø  ストローク o（ノルウェー語・デンマーク語）
    "\u00D8": "O",   # Ø  ストローク O
    "\u00DF": "ss",  # ß  エスツェット（ドイツ語）
    "\u0127": "h",   # ħ  ストローク h（マルタ語）
    "\u0126": "H",   # Ħ  ストローク H
    "\u01A1": "o",   # ơ  ホーン付き o（ベトナム語）
    "\u01AF": "U",   # Ư  ホーン付き U
    "\u01B0": "u",   # ư  ホーン付き u
    # --- 第2弾: allCountries.txt 全走査で追加（2026-03-26） ---
    # 北欧（デンマーク語・ノルウェー語・アイスランド語） 計62,795+666+781+204回
    "\u00E6": "ae",  # æ  合字 ae
    "\u00C6": "AE",  # Æ  合字 AE
    "\u00FE": "th",  # þ  ソーン（アイスランド語）
    "\u00DE": "TH",  # Þ  ソーン大文字
    # フランス語 計3,208+30回
    "\u0153": "oe",  # œ  合字 oe
    "\u0152": "OE",  # Œ  合字 OE
    # 西アフリカ諸語（ハウサ語・フラニ語等） 計3,098+40+19+1回
    "\u014B": "ng",  # ŋ  エング
    "\u014A": "NG",  # Ŋ  エング大文字
    "\u0272": "n",   # ɲ  パラタル n
    "\u019D": "N",   # Ɲ  パラタル N
    "\u0257": "d",   # ɗ  フック付き d
    "\u018A": "D",   # Ɗ  フック付き D
    "\u0253": "b",   # ɓ  フック付き b
    "\u0181": "B",   # Ɓ  フック付き B
    "\u0199": "k",   # ƙ  フック付き k
    "\u0198": "K",   # Ƙ  フック付き K
    "\u01B4": "y",   # ƴ  フック付き y
    "\u01B3": "Y",   # Ƴ  フック付き Y
    # その他（出現頻度 中〜低）
    "\u0254": "o",   # ɔ  オープン o（西アフリカ等）919回
    "\u0186": "O",   # Ɔ  オープン O
    "\u025B": "e",   # ɛ  オープン e（西アフリカ等）616回
    "\u0190": "E",   # Ɛ  オープン E
    "\u01DD": "e",   # ǝ  ターンド e（カメルーン等）339回
    "\u0268": "i",   # ɨ  ストローク i 28回
    "\u0192": "f",   # ƒ  フック付き f 26回
    "\u0167": "t",   # ŧ  ストローク t（サーミ語）35回
    "\u0166": "T",   # Ŧ  ストローク T
    "\u1E9E": "SS",  # ẞ  エスツェット大文字 2回
})


def _remove_accents(text: str) -> str:
    """アクセント記号除去 + NFD で分解できない特殊ラテン文字の置換。"""
    text = text.translate(_SPECIAL_LATIN_MAP)
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _remove_symbols(text: str) -> str:
    """括弧類・ダッシュ類の除去"""
    text = re.sub(r"[\(\)（）\[\]【】「」『』]", "", text)
    text = re.sub(r"[-－ー]", "", text)
    return text


# =========================================================
# Stage 2 : 実用正規化（比較用）
# =========================================================
def normalize_stage2(text: str) -> str:
    """
    Stage1 + アイン除去 + アクセント除去 + 小文字化 + 記号除去 + スペース除去。
    表記差を吸収して比較可能な形に統一。
    """
    text = normalize_stage1(text)
    text = _remove_ayn(text)
    text = _remove_accents(text)
    text = text.lower()
    text = _remove_symbols(text)
    text = text.replace(" ", "")
    return text


# =========================================================
# Stage 3 : 強制正規化（最大吸収）
# =========================================================
def normalize_stage3(text: str) -> str:
    """
    Stage2 + 全角英数字→半角、英数字・アンダースコア以外除去。
    ほぼ文字列骨格だけで比較する。
    """
    text = normalize_stage2(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\w]", "", text)
    return text


# =============================================================
# スタンドアロン テスト（python stage_matcher.py で実行可能）
# =============================================================
if __name__ == "__main__":
    import sys

    _BUILTIN_TESTS = [
        # (地名, 言語/備考)
        ("Qazımämmäd",       "アゼルバイジャン語 ı,ä"),
        ("Şamaxı",           "アゼルバイジャン語 ş,ı"),
        ("Łódź",             "ポーランド語 ł,ó"),
        ("Straße",           "ドイツ語 ß"),
        ("Þórshöfn",         "アイスランド語 þ,ö"),
        ("Þingvellir",       "アイスランド語 þ"),
        ("Ægissíða",         "アイスランド語 æ,í,ð"),
        ("Færøerne",         "デンマーク語 æ,ø"),
        ("Cœur",             "フランス語 œ"),
        ("Saint-Barthélemy", "フランス語 é"),
        ("Niŋo",             "西アフリカ ŋ"),
        ("Ɲamɛna",          "西アフリカ ɲ,ɛ"),
        ("Ɓobo-Dioulasso",  "西アフリカ ɓ"),
        ("Kɔrhogo",          "西アフリカ ɔ"),
        ("Hà Nội",           "ベトナム語 à,ộ"),
        ("Đà Nẵng",          "ベトナム語 đ,à,ẵ"),
        ("Ħal Luqa",         "マルタ語 ħ"),
        ("Sǝvan",            "カメルーン等 ǝ"),
        ("Roskilde Fjord",   "変化なし（参考）"),
        ("Al 'Ayn",          "アイン除去テスト"),
        ("Tokyo　 Station",  "全角スペース・連続空白"),
    ]

    def _print_table(names: list[tuple[str, str]]) -> None:
        w_in = max(len(n) for n, _ in names) + 2
        w_s1 = w_s2 = w_s3 = 4
        rows = []
        for name, note in names:
            s1 = normalize_stage1(name)
            s2 = normalize_stage2(name)
            s3 = normalize_stage3(name)
            w_s1 = max(w_s1, len(s1))
            w_s2 = max(w_s2, len(s2))
            w_s3 = max(w_s3, len(s3))
            rows.append((name, s1, s2, s3, note))

        hdr = (f"  {'入力':<{w_in}s}  {'Stage1':<{w_s1}s}  "
               f"{'Stage2':<{w_s2}s}  {'Stage3':<{w_s3}s}  備考")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for name, s1, s2, s3, note in rows:
            print(f"  {name:<{w_in}s}  {s1:<{w_s1}s}  "
                  f"{s2:<{w_s2}s}  {s3:<{w_s3}s}  {note}")

    if len(sys.argv) > 1:
        user_names = [(arg, "ユーザー入力") for arg in sys.argv[1:]]
        print("=== ユーザー指定テスト ===\n")
        _print_table(user_names)
    else:
        print("=== 組み込みテスト（21件） ===\n")
        _print_table(_BUILTIN_TESTS)
        print(f"\n  ヒント: 任意の地名をテストするには引数で渡してください。")
        print(f"  例: python stage_matcher.py Łódź Straße \"Hà Nội\"")
