# run_google_api_match.py 設計図報告書

## 1. 概要

GeoJSON の `title_from_google_api` から地名を抽出し、GeoNames の `name` / `alternatenames` と完全一致マッチングを行うスクリプト。

既存の司令塔①（`run_local_build.py`）が Excel の「修正後欧文地名」を入力とするのに対し、本スクリプトは Google API で取得した地名を入力とする。同一の `index_id` をキーに、既存マッチング結果との比較を行う。

### 位置付け

```
[既存パイプライン]
  Excel「修正後欧文地名」 → run_local_build.py → GeoNames マッチング

[本スクリプト]
  GeoJSON「title_from_google_api」 → run_google_api_match.py → GeoNames マッチング
                                                     ↓
                                              index_id で既存結果と比較
```

---

## 2. 入出力

### 入力

| ファイル | 説明 |
|----------|------|
| `geojson/by_region/{region}.geojson` | エリア別 GeoJSON（title_from_google_api を含む） |
| `geonames_master.pkl` | GeoNames 全データ（3.0 GB） |

### 出力

| ファイル | 説明 |
|----------|------|
| `output_google_api_match/{region}_google_api_match.xlsx` | マッチング結果 Excel |

---

## 3. 実行方法

```bash
cd /Users/itoumayumi/Desktop/project/scripts/pipeline_merged
python run_google_api_match.py --region <エリア名>
```

### エリア一覧

| 引数 | GeoJSON | 対応 Excel（既存パイプライン） |
|------|---------|-------------------------------|
| `cn000_asia` | cn000_asia.geojson | cn000_asia.xlsx, cn001_CN_asia.xlsx, cn002_KR-KP_asia.xlsx |
| `cn100_europe` | cn100_europe.geojson | cn100_europe.xlsx |
| `cn200_africa` | cn200_africa.geojson | cn200_africa.xlsx |
| `cn300_america` | cn300_america.geojson | cn300_america.xlsx |
| `cn450_oceania` | cn450_oceania.geojson | cn450_oceania.xlsx |

### 前提条件

1. `geonames_master.pkl` がプロジェクトルートに存在すること
2. `geojson/by_region/` に対象エリアの GeoJSON が存在すること

---

## 4. title_from_google_api のデータ形式

GeoJSON の各 Feature の `properties.title_from_google_api` は以下の4形式で格納されている。

| 形式 | 地名抽出 | 例 |
|------|----------|----|
| **dict + compound_code** | ○ 可能 | `{'compound_code': 'G275+PJR Agios Efstratios, Greece', 'global_code': '...'}` |
| **文字列（住所形式）** | △ 未対応 | `"Strada Cuza Vodă 35, Aiud 515200, Romania"` |
| **dict（global_code のみ）** | × 不可 | `{'global_code': '9VXCQMM5+X49'}` |
| **None** | × 不可 | キー自体が存在しない |

### compound_code からの地名抽出ロジック

```
入力: "G275+PJR Agios Efstratios, Greece"
              ↓
  1. Plus Code 部分を除去（最初のスペースで分割）
     → "Agios Efstratios, Greece"
  2. カンマ区切りの最初の要素を取得
     → "Agios Efstratios"
```

カンマ以降は地域名・国名であり、地名ではないため除外する。

### 文字列（住所形式）について

番地・郵便番号・通り名が混在し、地名の位置が不定。Phase2 として対応を予定。

---

## 5. マッチング仕様

### 5.1 マッチング方式

- **完全一致**のみ（あいまい検索なし）
- GeoNames `name` → `alternatenames` の順で検索（司令塔① Phase1 → Phase2 と同じ優先順位）
- 文字列の正規化は `unicodedata.normalize("NFC")` のみ（司令塔①と同一）

### 5.2 フィルタ

| フィルタ | 適用 | 理由 |
|----------|------|------|
| FCL フィルタ | **OFF** | Google API 地名にはカテゴリ情報がないため |
| 距離フィルタ | **OFF** | Google API 地名には緯度経度がないため |

### 5.3 国コード処理

- GeoJSON の `properties.country`（IOC 3-letter）を ISO 2-letter に変換
- 国ごとに GeoNames レコードを取得し、国別にマッチング（メモリ効率重視）
- 複合コード（例: `AFG／IRI`）は `／` で分割し、構成国すべてを対象とする

### 5.4 IOC → ISO 変換テーブル

`IOC_TO_ISO` 辞書でマッピング（約170カ国対応）。未対応コードはスキップし、Warning を出力する。

---

## 6. 処理フロー

```
1. GeoJSON 読み込み
   geojson/by_region/{region}.geojson → features

2. 地名抽出
   各 feature の title_from_google_api から compound_code 形式のみ地名を抽出
   → google_api_name 列に格納

3. geonames_master.pkl 読み込み（1回のみ）

4. 国ごとにマッチング
   for each country in GeoJSON:
     a. IOC 3-letter → ISO 2-letter 変換
     b. GeoNames レコード取得（by_ccode）
     c. name 辞書 / alternatenames 辞書を構築
     d. 各 feature の google_api_name を完全一致検索
     e. 結果を ga_judge, ga_matched_stage, ga_matched 等に格納

5. 既存結果との比較
   GeoJSON の matched_flag（T/×）と ga_matched を突合
   → comparison 列に分類ラベルを付与

6. Excel 出力
```

---

## 7. 出力列定義

### GeoJSON 由来の列

| 列名 | 内容 |
|------|------|
| `index_id` | 一意の ID（Excel・GeoJSON 共通キー） |
| `english_title` | ローカル欧文地名（「修正後欧文地名」相当） |
| `country` | IOC 3-letter 国コード |
| `lo_fcl` | ローカル側カテゴリ（P/A/S/T） |
| `existing_matched_flag` | 既存マッチング結果（T = マッチ済 / × = 0マッチ） |

### 地名抽出の列

| 列名 | 内容 |
|------|------|
| `google_api_name` | compound_code から抽出した地名（抽出不可の場合は空） |
| `source_type` | データ形式（compound_code / address_string / global_code_only / none） |

### マッチング結果の列（接頭辞 `ga_`）＿「ga_」 は Google Api の略

| 列名 | 内容 |
|------|------|
| `ga_judge` | 1 / 2+ / 0（マッチ件数。抽出不可の場合は空） |
| `ga_matched_stage` | hit-name-1 / hit-name-2+ / hit-alter-1 / hit-alter-2+（空欄=未マッチ） |
| `ga_matched` | TRUE / FALSE（抽出不可の場合は空） |
| `ga_hit_count` | マッチした GeoNames レコード数 |
| `ga_matched_geonameid` | マッチした geonameid（複数は ` \| ` 区切り） |
| `ga_matched_fcl` | マッチした GeoNames の fcl |
| `ga_matched_fcode` | マッチした GeoNames の fcode |
| `ga_matched_gn_name` | マッチした GeoNames の name |
| `ga_matched_ccode` | マッチした GeoNames の country code（ISO 2-letter） |

### 比較の列

| 列名 | 内容 |
|------|------|
| `comparison` | 既存結果との比較ラベル（下表参照） |

---

## 8. 比較ラベル（comparison 列）

| ラベル | 既存 matched_flag | GA マッチ | 意味 | 価値 |
|--------|-------------------|-----------|------|------|
| **★new_match** | × | ○ | 既存 0マッチ → Google API でマッチ | **最も価値が高い** |
| **confirmed** | T | ○ | 両方でマッチ | 信頼度の確認 |
| **existing_only** | T | × | 既存のみマッチ（GA で名前抽出できたが GeoNames 不一致） | — |
| **both_zero** | × | × | 両方とも 0マッチ | 要調査 |
| **ga_only** | —（不明） | ○ | 既存結果が不明だが GA でマッチ | — |
| **no_google_data** | — | — | Google API 地名が抽出できなかった | — |

---

## 9. Excel シート構成

| シート名 | 内容 |
|----------|------|
| **all** | 全件（全 feature）。抽出不可も含む |
| **new_match** | comparison = ★new_match の行のみ |
| **confirmed** | comparison = confirmed の行のみ |
| **both_zero** | comparison = both_zero の行のみ |
| **summary** | 統計一覧表 |

---

## 10. 司令塔①（run_local_build.py）との違い

| 項目 | 司令塔① | 本スクリプト |
|------|---------|-------------|
| 入力データ | Excel「修正後欧文地名」 | GeoJSON「title_from_google_api」 |
| 入力形式 | Excel (.xlsx) | GeoJSON (.geojson) |
| 地名の前処理 | 略語展開（edit_comma_abb） | compound_code からの抽出 |
| FCL フィルタ | ON（設定可） | OFF |
| 距離フィルタ | ON（設定可） | OFF |
| マッチング対象 | 国別 GeoNames（by_ccode） | 国別 GeoNames（by_ccode） |
| マッチング方式 | NFC 完全一致 | NFC 完全一致（同一） |
| GeoNames 辞書 | geonames_loader.py 経由 | 直接 pkl 読み込み（geopandas 非依存） |
| 出力 | Phase1/Phase2 別 Excel + 統計表 | 統合 Excel + 比較ラベル |

---

## 11. 既知の制限事項

| 項目 | 内容 | 対応予定 |
|------|------|----------|
| 文字列（住所形式） | 番地・郵便番号が混在し地名抽出困難 | Phase2 |
| global_code のみ | Plus Code のみで地名情報なし | 対応不可 |
| None | title_from_google_api がない Feature | 対応不可（GeoJSON 構造上の制限） |
| geonames_master.pkl 読込時間 | 3GB のため読み込みに数分かかる | pkl 分割は将来検討 |
| IOC_TO_ISO 未対応コード | 一部の自治区・特殊コードが未登録の場合あり | 発見次第追加 |

---

## 12. 今後の拡張予定

### Phase2: 文字列（住所形式）からの地名抽出

住所形式の `title_from_google_api`（例: `"Strada Cuza Vodă 35, Aiud 515200, Romania"`）から地名を抽出する方法の検討。

候補案:
- カンマ区切りで末尾を国名として除外し、残りから郵便番号・番地パターンを除外
- 既知の `english_title` と住所文字列の部分一致で逆引き
- 既存マッチ済み行の `english_title` と住所の対応関係をパターン学習

### confirmed の信頼度評価

`comparison = confirmed` の行について、既存マッチの `geonameid` と `ga_matched_geonameid` が一致するか検証し、信頼度スコアを付与する。

---

*作成日: 2026-03-26*
