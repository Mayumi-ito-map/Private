"""
expand_quote_variants.py

地名に含まれる「記号ゆれ」（アポストロフィ・引用符・アイン等）を
候補として複数形で生成する。司令塔②で Stage マッチング前に使用。

対象外（処理しない）:
  - "," "." … 司令塔①で扱うため
  - "-" … Stage2/3 で吸収されるため

例: "d'Or" に ʻ が含まれる場合 → "d'Or", "d'Or", "d'Or" 等の候補を追加
"""

from __future__ import annotations

from typing import Sequence

# 地名で表記ゆれになりやすい記号。互いに置換した候補を生成する。
# symbol_summary では ' と ' のみ出現したが、司令塔②の入力（output_match の normalized_name）
# には Excel の読み込み・他ソース由来で ʻ ʿ 等が含まれる場合があり、7文字にしておくと候補が増えて効果が出る。
# 対象外: "," "." "-" (司令塔①／Stage2/3)、U+0022 は二重引用符のため別扱い。
QUOTE_LIKE_CHARS = [
    "'",   # U+0027 ASCII apostrophe
    "'",   # U+2019 RIGHT SINGLE QUOTATION MARK
    "`",   # U+0060 grave accent
    "ʻ",   # U+02BB MODIFIER LETTER TURNED COMMA (Hawaiian ʻokina, アラビア語 hamza 等)
    "ʿ",   # U+02BF MODIFIER LETTER LEFT HALF RING (Arabic ʿayn 等)
    "´",   # U+00B4 acute accent
    "ʼ",   # U+02BC MODIFIER LETTER APOSTROPHE
]


def _replace_quote_like(text: str, replacement: str) -> str:
    """text 内の QUOTE_LIKE_CHARS のいずれかをすべて replacement に置換する。"""
    result = text
    for c in QUOTE_LIKE_CHARS:
        result = result.replace(c, replacement)
    return result


def expand_quote_variants(text: str) -> list[str]:
    """
    1つの地名候補について、記号ゆれの候補を生成する。
    元の文字列は必ず含める。

    - 文字列に QUOTE_LIKE_CHARS が1つも無い場合: [text] のみ返す（展開しない）。
    - 1つでも含まれる場合: 元 + 「記号を各キャラクタに統一した」候補を返す（漏れなし）。

    Args:
        text: 地名候補 1件

    Returns:
        元 + 記号ゆれで増えた候補のリスト（重複除去）
    """
    if not text or not isinstance(text, str):
        return []
    s = text.strip()
    if not s:
        return []
    has_any = any(c in s for c in QUOTE_LIKE_CHARS)
    if not has_any:
        return [s]
    seen = {s}
    result = [s]
    for r in QUOTE_LIKE_CHARS:
        variant = _replace_quote_like(s, r)
        if variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result


def expand_candidates_quote_variants(candidates: Sequence[str]) -> list[str]:
    """
    複数の地名候補それぞれを記号ゆれ展開し、重複を除いて1つのリストにまとめる。

    Args:
        candidates: normalized_name から得た候補リスト

    Returns:
        元の候補 + 記号ゆれで増えた候補（重複除去、順序は元を優先）
    """
    if not candidates:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        for s in expand_quote_variants(c):
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result
