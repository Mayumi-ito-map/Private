"""
expand_synonyms.py

地名の一般語・接頭辞/接尾辞の同義語展開。
司令塔②で judge==0 の候補に対して、Stage マッチング前に候補を増やすために使用する。

例: "Mt. Everest" → ["Mt. Everest", "Mount Everest", "Mt Everest"]
    "St. John's" → ["St. John's", "Saint John's", "St John's"]
"""

from __future__ import annotations

import re
from typing import Sequence

# 接頭辞の同義語マップ: (前方一致する接頭辞, 置換候補のリスト)
# 元の表記は必ず残すため、ここでは「追加で生成する」表記を列挙する
SYNONYM_PREFIXES: list[tuple[str, list[str]]] = [
    # 山
    ("Mt. ", ["Mount ", "Mt "]),
    ("Mount ", ["Mt. ", "Mt "]),
    ("Mt ", ["Mount ", "Mt. "]),
    # 聖人・サン
    ("St. ", ["Saint ", "St "]),
    ("Saint ", ["St. ", "St "]),
    ("St ", ["Saint ", "St. "]),
    # アラビア系「山」
    ("Jebel ", ["Jabal ", "J. ", "Djebel "]),
    ("Jabal ", ["Jebel ", "J. ", "Djebel "]),
    ("J. ", ["Jebel ", "Jabal ", "Djebel "]),
    ("Djebel ", ["Jebel ", "Jabal ", "J. "]),
    # 湖・河川・湾など（略語とフルスペル）
    ("L. ", ["Lake ", "L "]),
    ("Lake ", ["L. ", "L "]),
    ("R. ", ["River ", "R "]),
    ("River ", ["R. ", "R "]),
    ("C. ", ["Cape ", "C "]),
    ("Cape ", ["C. ", "C "]),
    ("Pt. ", ["Point ", "Pt "]),
    ("Point ", ["Pt. ", "Pt "]),
    ("Str. ", ["Strait ", "Strait of ", "Str "]),
    ("Strait ", ["Str. ", "Str "]),
    ("B. ", ["Bay ", "B "]),
    ("Bay ", ["B. ", "B "]),
    ("G. ", ["Gulf ", "G "]),
    ("Gulf ", ["G. ", "G "]),
    # 島
    ("I. ", ["Island ", "Is. ", "I "]),
    ("Is. ", ["Island ", "I. ", "I "]),
    ("Island ", ["I. ", "Is. ", "I "]),
]


def expand_place_name_synonyms(text: str) -> list[str]:
    """
    1つの地名候補に対して、接頭辞の同義語展開を行い、候補リストを返す。
    元の文字列は必ず先頭に含める。重複は除去する。

    Args:
        text: 地名候補 1件（例: "Mt. Everest"）

    Returns:
        展開後の候補リスト（例: ["Mt. Everest", "Mount Everest", "Mt Everest"]）
    """
    if not text or not isinstance(text, str):
        return []
    s = text.strip()
    if not s:
        return []
    seen = {s}
    result = [s]
    for prefix, replacements in SYNONYM_PREFIXES:
        if not s.startswith(prefix):
            continue
        rest = s[len(prefix) :]
        for r in replacements:
            # "Jabal" のみ末尾スペースなしの可能性があるので rest の先頭がスペースなら合わせる
            variant = r.rstrip() + rest if rest.startswith(" ") else r + rest
            if variant not in seen:
                seen.add(variant)
                result.append(variant)
    return result


def expand_candidates_synonyms(candidates: Sequence[str]) -> list[str]:
    """
    複数の地名候補それぞれを同義語展開し、重複を除いて1つのリストにまとめる。
    司令塔②で parse_normalized_name() の直後に呼ぶ想定。

    Args:
        candidates: normalized_name から得た候補リスト

    Returns:
        元の候補 + 同義語展開で増えた候補（重複除去、順序は元を優先）
    """
    if not candidates:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        for s in expand_place_name_synonyms(c):
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result
