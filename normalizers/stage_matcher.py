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
