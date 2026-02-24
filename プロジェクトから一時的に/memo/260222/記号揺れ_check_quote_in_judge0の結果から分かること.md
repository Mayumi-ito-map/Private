# check_quote_in_judge0.py の結果から分かること

## 診断結果（要約）

| 項目 | 値 |
|------|-----|
| judge==0 の行数（全国合計） | 3,390 |
| そのうち ' または ' を1つでも含む行数 | 238 |
| 割合 | 7.0% |

例（最大5件）:
- cn004_AE_アラブ首長国連邦_result.xlsx … "R'as al Khaymah", "Al 'Ayn"
- cn006_YE_イエメン_result.xlsx … "J. an Nabī Shu'ayb", "Ramlat as Sab'atayn"
- cn007_IL_イスラエル_result.xlsx … "Wādī al 'Arabah"

---

## ここから分かること

### 1. 「2文字でも対象は 0 ではなかった」

- judge==0 のうち **238 行（7%）** に、' (U+0027) または ' (U+2019) が含まれている。
- つまり **2文字（' と '）にしたときも、記号ゆれの「展開対象」は 0 ではなく、238 行分は候補が増えていた**可能性が高い。
- 以前「Base と全く同じ結果」としていたのは、おそらく **行数（rows_with_hit / rows_still_0）** に注目した比較。**候補数（total_candidates）** は 2 文字版の方が多くなっていた可能性がある。

### 2. 地域的な偏り

- 例は **アラブ首長国連邦・イエメン・イスラエル** など西アジア。
- 地名中の **アポストロフィ** は、アラビア語の ʻayn などの転写でよく使われる。
- 記号ゆれの効果が出やすいのは、**そうした地域の judge==0 の行**と考えられる。

### 3. 2文字で「行数」が変わらなかった理由の推測

- 238 行では候補は増えていたが、**増えた候補のどれも GeoNames と一致しなかった**可能性がある。
- 例えばローカルは **'** で、GeoNames は **ʿ (U+02BF)** で登録されている場合、**' と ' の 2 文字だけ**では「ʿ にそろえた候補」を作らないため、マッチしない。
- **7 文字**（' ' ` ʻ ʿ ´ ʼ）にすると、**ʿ にそろえた候補**も試せるので、西アジアでヒットが増えた、という整理と矛盾しない。

### 4. openpyxl の警告について

- `Cannot parse header or footer so it will be ignored` は、Excel のヘッダー／フッターを openpyxl が解釈できなかったという警告。
- **データの読み取りには影響しない**ので、無視してよい。

---

## まとめ

- judge==0 の **7% に ' または ' が含まれており**、2 文字版でも記号ゆれの対象は 0 ではなかった。
- それでも **行数ベースの結果が Base と変わらなかった**のは、増えた候補が GeoNames 側の表記（例: ʿ）と一致せず、**2 文字では試せる記号の幅が足りなかった**ためと考えられる。
- 7 文字に戻している現状の設定は、この診断結果とも整合する。

---

## 2文字版を後から実行するとき（セットで理解を深める用）

- **2文字版モジュール**: `normalizers/expand_quote_variants_2chars.py` を別名で用意済み。
- **司令塔②で 2文字版の結果を出す手順**:
  1. `run_stage_match_quote_variants.py` の import を  
     `from normalizers.expand_quote_variants_2chars import expand_candidates_quote_variants` に変更。
  2. `candidates = expand_candidates_quote_variants(candidates)` はそのまま（関数名は同じ）。
  3. `OUTPUT_DIR` を例: `output_match_results_quote_variants_2chars` に変更。
  4. 実行すると 2文字版の結果が別フォルダに出力される。7文字版の結果と比較できる。
- **セットとして参照するもの**: 本メモ ＋ 「記号揺れ_応答の時系列まとめ.md」＋ 2文字版 `expand_quote_variants_2chars.py`。
