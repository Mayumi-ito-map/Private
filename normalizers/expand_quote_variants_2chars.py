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
    "\u0027",   # U+0027 ASCII apostrophe (')
    "\u2019",   # U+2019 RIGHT SINGLE QUOTATION MARK (')
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


# -----------------------------------------------------------------------------
# 試し用の単語（地名5つ）・テスト関数
# このファイルを直接実行したときだけ動く。司令塔②で import したときは実行されない。
# -----------------------------------------------------------------------------

_TEST_PLACE_NAMES = [
    "d'Or",                    # U+0027 を含む
    "Al \u2019Ayn",            # U+2019 を含む（RIGHT SINGLE QUOTATION MARK）
    "R'as al Khaymah",         # U+0027 を含む
    "Tokyo",                   # 記号なし（展開されない）
    "J. an Nabī Shu'ayb",      # U+0027 を含む
]


def _run_test() -> None:
    """試し用の単語で expand_quote_variants / expand_candidates_quote_variants の動きと結果を表示する。"""
    print("=== expand_quote_variants_2chars テスト（2文字版） ===\n")
    print("QUOTE_LIKE_CHARS: ' (U+0027), ' (U+2019)\n")

    print("--- 1件ずつ expand_quote_variants(text) ---")
    for name in _TEST_PLACE_NAMES:
        variants = expand_quote_variants(name)
        # 見やすくするため repr でアポストロフィの種類が分かるようにする
        print(f"  入力: {repr(name)}")
        print(f"  → {len(variants)} 件: {[repr(v) for v in variants]}\n")

    print("--- 全件まとめて expand_candidates_quote_variants(candidates) ---")
    expanded = expand_candidates_quote_variants(_TEST_PLACE_NAMES)
    print(f"  入力候補数: {len(_TEST_PLACE_NAMES)}")
    print(f"  展開後（重複除く）: {len(expanded)} 件")
    for i, s in enumerate(expanded, 1):
        print(f"    {i}. {repr(s)}")
    print("\n=== テスト終了 ===")


if __name__ == "__main__":
    _run_test()
