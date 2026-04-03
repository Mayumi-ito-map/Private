# run_local_build.py 設計図報告書

## 1. 概要

`run_local_build.py` は **司令塔①** として、合体 Excel の「修正後欧文地名」を GeoNames データベースと照合し、完全一致マッチングを行うスクリプトである。国毎モードと全世界モードの2つの実行モードを備え、Phase1（name 完全一致）→ Phase2（alternatenames 完全一致）の2段階マッチングを実施する。

---

## 2. 責務と境界

### 2.1 本スクリプトの責務

| 責務 | 説明 |
|------|------|
| 入力読込 | 合体 Excel（`excel_local_merged/*.xlsx`）の「修正後欧文地名」を読む |
| 候補生成 | `normalizers.edit_comma_abb` により 1地名 → N候補（略語展開・カンマ並び替え） |
| Phase1 マッチング | GeoNames の `[name]` で完全一致 → インメモリ保持 |
| Phase2 マッチング | Phase1 で hit-0 の行のみ `[alternatenames]` で完全一致（hit-2+ は除外） |
| 出力 | Phase1 と Phase2 をマージした状態で Excel 出力 |

### 2.2 本スクリプトの責務外

- **Stage1/2/3**（同義語展開・曖昧マッチング）→ 司令塔②（`run_stage_match.py`）の責務
- **Leaflet 用 GeoJSON 出力** → `export_for_leaflet.py` の責務
- **GeoNames マスタの構築** → `build_geonames_*.py` の責務

---

## 3. アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        run_local_build.py（司令塔①）                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐ │
│  │ 合体 Excel   │     │ edit_comma_abb   │     │ GeoNames マッチング      │ │
│  │ 修正後欧文地名 │ ──► │ 1→N 候補生成     │ ──► │ Phase1: [name] 完全一致  │ │
│  └──────────────┘     └──────────────────┘     │ Phase2: [alternatenames] │ │
│         │                       │              └────────────┬──────────────┘ │
│         │                       │                           │               │
│         ▼                       ▼                           ▼               │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐ │
│  │ geonames_    │     │ FCL フィルタ     │     │ 距離計算（Haversine）   │ │
│  │ loader       │     │ lo_fcl → gn_fcl │     │ 距離閾値で候補絞り込み  │ │
│  └──────────────┘     └──────────────────┘     └─────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  出力                                                                       │
│  • output_match_name/*_name.xlsx（Phase1 結果・judge 別シート）              │
│  • output_match_alternatenames/*_alternate.xlsx（Phase2 マージ結果）         │
│  • output_match/tower1_world_stats.xlsx（統計表 + 全行）                     │
│  • output_match_worldwide/*_terrain_phase1_2.xlsx（全世界モード時）           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. モード設計

### 4.1 国毎モード（デフォルト）

| 項目 | 内容 |
|------|------|
| データソース | `geonames_master.pkl`（by_ccode で国別インデックス） |
| グループ化 | Excel の `cc` 列で国毎にグループ化 |
| 海外領土 | `config/overseas_territories.json` で複数国コードに展開 |
| 出力先 | `output_match_name/`, `output_match_alternatenames/`, `output_match/` |

### 4.2 全世界モード（`--worldwide`）

| 項目 | 内容 |
|------|------|
| データソース | `geonames_worldwide_terrain.pkl`（海・山地名に特化） |
| 対象行 | `num` 列が `NUM_FOR_WORLDWIDE_MATCHING` に含まれる行のみ |
| 処理単位 | 合体ファイル単位で一括マッチング（国別分割なし） |
| 出力先 | `output_match_worldwide/*_terrain_phase1_2.xlsx` |

---

## 5. データフロー

### 5.1 国毎モードの処理フロー

```
合体 Excel 読込
    │
    ├─ cc 列でグループ化
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 各国ループ                                                   │
│                                                             │
│  1. get_geonames_for_country(db, cc, overseas_map, "name")  │
│     → placename_dict 構築                                   │
│                                                             │
│  2. process_one_country_phase1()                            │
│     - NFC 正規化                                            │
│     - edit_comma_abb（略語展開）                             │
│     - _add_match_columns（name 完全一致）                    │
│     - FCL フィルタ適用                                       │
│     - 距離計算・距離閾値で候補絞り込み                        │
│                                                             │
│  3. process_one_country_phase2()                            │
│     - name_judge == "0" の行のみ対象                        │
│     - alternatenames で再マッチング                          │
│                                                             │
│  4. _merge_phase2_into_phase1()                             │
│     - Phase1 全行をベースに Phase2 結果を上書き              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
全国の結果を concat → Excel 出力（マージファイル単位）
```

### 5.2 Phase2 の対象条件

| Phase1 結果 | Phase2 対象 | 理由 |
|-------------|------------|------|
| hit-name-1 | 対象外 | 既に1件確定 |
| hit-name-2+ | 対象外 | 複数候補のため alternate 検索は行わない |
| hit-name-0 | **対象** | name でヒットしなかった行のみ alternatenames で再検索 |

---

## 6. 主要コンポーネント

### 6.1 パス・定数

| 定数 | 用途 |
|------|------|
| `BASE_DIR`, `EXCEL_DIR` | 入出力ディレクトリ |
| `TARGET_COL` | 対象列「修正後欧文地名」 |
| `FCL_FILTERS` | local_fcl ごとの GeoNames fcl 制限（P→P, A→A/L, S→S/V, T→H/T） |
| `MERGED_PATTERNS` | 処理対象の合体ファイル名パターン |
| `LOCAL_LAT_LON_COLUMNS` | ローカル緯度経度列の候補（lat/long, latitude/longitude, 緯度/経度） |
| `DISTANCE_THRESHOLDS` | カテゴリ別の距離閾値（km）。閾値超過の候補を除外 |
| `ENABLE_DISTANCE_THRESHOLD` | 距離閾値フィルタの ON/OFF |

### 6.2 コア関数一覧

| 関数 | 責務 |
|------|------|
| `load_overseas_territories()` | 海外領土設定 JSON の読込 |
| `match_geonames_candidates()` | 候補名リストと placename_dict の完全一致検索（geonameid ユニーク化） |
| `_haversine_km()`, `_calc_distance_row()` | 2点間距離計算（Haversine） |
| `ensure_local_lat_lon()` | Excel の緯度経度列を `local_lat` / `local_lon` に統一 |
| `_add_match_columns()` | マッチング結果列の追加（hits, judge, fcl, fcode, distance, matched_*）。全候補を `" | "` 区切りで出力 |
| `_parse_distance_list()` | distance 列をリストに変換。`" | "` 区切り対応。無効値は float('inf') |
| `_apply_distance_threshold_filter()` | 距離閾値で候補を絞り込み。閾値超過を除外し judge を更新 |
| `process_one_country_phase1()` | Phase1 処理（name 完全一致） |
| `process_one_country_phase2()` | Phase2 処理（alternatenames 完全一致） |
| `_merge_phase2_into_phase1()` | Phase2 結果を Phase1 にマージ |
| `_reorder_columns_for_output()` | 出力用列順の整列 |
| `_write_phase1_excel()`, `_write_phase2_excel()` | Excel 出力 |
| `_build_tower1_stats()` | 統計表の構築 |
| `main()`, `main_worldwide()` | エントリポイント |

### 6.3 外部依存

| モジュール | 役割 |
|------------|------|
| `geonames_loader` | `load_master_pkl`, `get_geonames_for_country`, `build_placename_dict` |
| `normalizers.edit_comma_abb` | 1地名 → N候補（カンマ並び替え・略語展開） |
| `pandas`, `openpyxl` | データ処理・Excel 入出力 |

---

## 7. 出力設計

### 7.1 出力ファイル構成

| 出力先 | ファイル | 内容 |
|--------|----------|------|
| `output_match_name/` | `{base}_name.xlsx` | Phase1 結果。シート: all, judge_0, judge_1, judge_2plus |
| `output_match_alternatenames/` | `{base}_alternate.xlsx` | Phase2 マージ結果。全行出力、Phase2 対象外は alternate 列を空欄 |
| `output_match/` | `tower1_world_stats.xlsx` | Sheet1: 国別統計表、all: 全行データ |
| `output_match_worldwide/` | `{base}_terrain_phase1_2.xlsx` | 全世界モード時の Phase1+2 結果 |

### 7.2 追加列（GeoNames マージ列）

| 列名 | 説明 |
|------|------|
| `edited_name` | 略語展開後の候補リスト（元は list、出力時は `\|` 区切り文字列） |
| `geonames_name_hits` | Phase1 のヒットレコードリスト |
| `hit_name_len`, `name_judge` | Phase1 のヒット数・判定（0/1/2+） |
| `geonames_alternatenames_hits` | Phase2 のヒットレコードリスト |
| `hit_alter_len`, `alter_judge` | Phase2 のヒット数・判定 |
| `matched_stage`, `matched` | Phase2 のマッチステージ・マッチ有無 |
| `fcl`, `fcode` | GeoNames の feature class / feature code |
| `distance` | ローカル緯度経度と GeoNames の距離（km）。複数候補時は `" | "` 区切りで全候補を出力 |
| `matched_geonameid`, `matched_lat`, `matched_lon` | 採用候補の ID・緯度・経度 |

### 7.3 列順序

`local_lat`, `local_lon` の直後に GeoNames マージ列（`GEONAMES_MERGE_ORDER`）を配置。`run_stage_match` や `export_for_leaflet` との互換性を確保。

---

## 8. 設計の特徴・利点

### 8.1 関心の分離

- **司令塔①**: 完全一致マッチング（Phase1/2）のみ
- **司令塔②**: 同義語展開・曖昧マッチング（Stage1/2/3）
- **geonames_loader**: GeoNames データの読込・辞書構築
- **edit_comma_abb**: 地名の正規化・候補生成

### 8.2 2モードの統一設計

国毎モードと全世界モードで、Phase1 → Phase2 → マージ の流れを共通化。全世界モードは `_process_worldwide_one_file` 内で同様の処理を実装し、データソース（pkl）と対象行の絞り込みのみを切り替え。

### 8.3 設定の切り替えポイント

- **FCL_FILTERS**: `enabled` でカテゴリ制限の ON/OFF、`gn_allowed` で GeoNames の許容 fcl を設定
- **MERGED_PATTERNS**: テスト時は1件のみにすると高速化可能
- **NUM_FOR_WORLDWIDE_MATCHING**: 全世界モードの対象 num を変更可能

### 8.4 統計の一貫性

`_build_tower1_stats` で Phase1/Phase2 の行数・候補数・パーセンテージを計算。`tower1_world_stats.xlsx` に統計表と全行データの両方を出力し、後続分析や検証を容易にする。

---

## 9. 実行方法

```bash
# 国毎モード（デフォルト）
python -m scripts.pipeline_merged.run_local_build

# 全世界モード（海・山地名）
python -m scripts.pipeline_merged.run_local_build --worldwide
```

---

## 10. 前提・制約

以下の前提を踏まえて設計・運用する。

| 前提 | 説明 |
|------|------|
| ローカル緯度経度 | 必ずしも正確ではない。近似値や誤りの可能性がある |
| ローカルカテゴリ（P,A,S,T） | 必ずしも正確ではない。誤りの可能性がある |

---

## 11. 前提条件

1. **合体 Excel**: `scripts.prepare_excel.merge_excel` で作成済み
2. **geonames_master.pkl**: プロジェクトルートに存在（国毎モード）
3. **geonames_worldwide_terrain.pkl**: `build_geonames_worldwide_terrain.py` で生成（全世界モード）
4. **config/overseas_territories.json**: 海外領土設定（国毎モード）

---

## 12. 調査報告: AZE 0マッチ原因分析（2026-03-26）

### 12.1 調査の経緯

アゼルバイジャン（AZE）を対象に、GeoJSON 上で `matched_flag=×`（0マッチ）となっている 10件の地名について、`data/AZ.txt` および `allCountries.txt`（1,340万行）の `name`・`alternatenames` 列との完全一致を調査した。

### 12.2 調査結果

| 地名 | name 列 | alternatenames 列 | 状況 |
|------|---------|-------------------|------|
| Ordubad | **あり** | **あり** | データにあるのに 0マッチ |
| Qazax | **あり** | **あり** | 同上 |
| Neftçala | **あり** | **あり** | 同上 |
| Şamaxı | なし | **あり** | alt にはある |
| Mingäçevir | なし | **あり** | alt にはある |
| Qazımämmäd | なし | なし | 完全一致ではデータになし |
| Siyäzän | なし | なし | 同上 |
| Dänizkänar | なし | なし | 同上 |
| Xankändi | なし | なし | 同上 |
| Xocavänd | なし | なし | 同上 |

`allCountries.txt` でも `AZ.txt` と同一の結果であり、国別ファイル特有の欠損ではないことを確認。

### 12.3 特定された原因（2点）

#### 原因1: FCL フィルタによる除外

`run_local_build.py` の `FCL_FILTERS`（73〜78行目）により、Excel 側の `lo_fcl` に対して GeoNames 側の `fcl` が制限されている。例えば `lo_fcl=S`（ポイント）の行に対し GeoNames 側が `fcl=P`（都市）の場合、名前が完全一致していても除外される。

```python
FCL_FILTERS = {
    "P": {"enabled": True, "gn_allowed": ("P",)},
    "A": {"enabled": True, "gn_allowed": ("A", "L")},
    "S": {"enabled": True, "gn_allowed": ("S", "V")},
    "T": {"enabled": True, "gn_allowed": ("H", "T")},
}
```

Ordubad, Qazax, Neftçala は GeoNames 上で `fcl=P` であり、Excel 側カテゴリとの不一致で除外された可能性がある。

#### 原因2: 距離閾値フィルタによる除外

`DISTANCE_THRESHOLDS`（94〜102行目）により、ローカル座標と GeoNames 座標の距離が閾値を超える候補が除外される。特に `S: 10km` は厳格であり、ローカル座標に誤りがある場合にマッチ済み候補が 0 に落とされる。

```python
DISTANCE_THRESHOLDS = {
    "P": 150,
    "A": 500,
    "S": 10,
    "T": None,
}
ENABLE_DISTANCE_THRESHOLD = True
```

### 12.4 0マッチ10件の補足事項

0マッチ（`matched_flag=×`）の10件は、マッチ済み（`T`）の53件と GeoJSON 上の構造が異なる。

| 項目 | マッチ済み（T） | 0マッチ（×） |
|------|----------------|-------------|
| `geometry.coordinates` | 数値（緯度経度あり） | `[null, null]` |
| `kml_*` 系プロパティ | あり | なし |
| `title_from_google_api` | あり | **キー自体が存在しない** |

この構造差により、0マッチの行には Google API 情報を活用できない。

### 12.5 今後の `run_local_build.py` 見直し方針

上記2点の原因を踏まえ、以下の見直しを予定している。

- **FCL フィルタ**: `lo_fcl` と `gn_allowed` の対応が妥当か再検証。必要に応じて許容範囲の拡大を検討
- **距離閾値**: ローカル座標の精度が低い国・カテゴリに対し、閾値の緩和または無効化を検討
- **切り分け手順**: FCL フィルタと距離フィルタを一時的に無効化（`enabled=False`, `ENABLE_DISTANCE_THRESHOLD=False`）して再実行し、名前一致の有無を確認してからフィルタ条件を調整する

---

## 13. 参照: 正規化・あいまいマッチング関連

`stage_matcher.py` のダイアクリティカル対応強化（`_SPECIAL_LATIN_MAP` 48文字追加）および司令塔②の設計詳細は、以下の別ドキュメントに記載。

→ **`run_stage_match_設計図報告書.md`**（第7章〜第9章）

---

*作成日: 2025-03-10 | 更新日: 2026-03-31*
