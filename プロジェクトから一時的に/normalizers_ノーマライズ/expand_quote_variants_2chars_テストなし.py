"""
expand_quote_variants_2chars.py（2文字版）

記号ゆれの「2文字版」: symbol_summary.xlsx の結果（' と ' のみ出現）に合わせた版。
比較用に別名で保持。司令塔②で 2 文字版の結果を出したいときは、
  from normalizers.expand_quote_variants_2chars import expand_candidates_quote_variants
  candidates = expand_candidates_quote_variants(candidates)
  OUTPUT_DIR = ... / "output_match_results_quote_variants_2chars"
のように差し替えて実行する。

対象: ' (U+0027), ' (U+2019) のみ。候補は最大 1+2＝3 種類。
対象外: "," "." "-" (司令塔①／Stage2/3)、U+0022 は二重引用符のため別扱い。
"""

from __future__ import annotations

from typing import Sequence

QUOTE_LIKE_CHARS = [
    "'",   # U+0027 ASCII apostrophe
    "'",   # U+2019 RIGHT SINGLE QUOTATION MARK
]


def _replace_quote_like(text: str, replacement: str) -> str:
    """text 内の QUOTE_LIKE_CHARS のいずれかをすべて replacement に置換する。"""
    result = text
    for c in QUOTE_LIKE_CHARS:
        result = result.replace(c, replacement)
    return result


def expand_quote_variants(text: str) -> list[str]:
    """
    1つの地名候補について、記号ゆれの候補を生成する（2文字版）。
    元の文字列は必ず含める。' または ' が無い場合は [text] のみ返す。
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
    複数の地名候補それぞれを記号ゆれ展開し、重複を除いて1つのリストにまとめる（2文字版）。
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
