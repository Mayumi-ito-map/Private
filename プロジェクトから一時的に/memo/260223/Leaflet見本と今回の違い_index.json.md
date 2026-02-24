# Leaflet見本（index_fr.html）と今回の地図で「index.json が見つからない」が起きる理由

## 見本（index_fr.html）の仕組み

- **国は1つだけ（フランス）**。国を切り替えるプルダウンはない。
- データの読み込みは **&lt;script src="data_fr.js"&gt;** で行っている。
  - `data_fr.js` の中身は **GeoJSON を JavaScript の変数 `geoJsonData` に代入しただけ**のファイル。
  - ブラウザが HTML を表示するときに、**HTML と同じフォルダの `data_fr.js` を「ページの基準 URL」で取得**する。
- `main_fr.js` では **fetch は使っていない**（フォールバックで fetch する分支はあるが、通常は `geoJsonData` が既に存在するので使われない）。
- **index.json は存在しない**。国一覧もない。

→ 見本では「別ファイルを fetch で読む」処理をしていないため、**index.json が見つからない問題は起きない**。

---

## 今回の地図（leaflet_map.html）の仕組み

- **193国をプルダウンで切り替える**仕様。
  - 国一覧 → **index.json**
  - 選択した国のデータ → **cn002_AZ_アゼルバイジャン.geojson** などの GeoJSON ファイル
- これらを **fetch()** で「動的に」読み込んでいる。
  - ページを開いたとき: `fetch("index.json")` で国一覧を取得
  - 国を選んだとき: `fetch(ファイル名)` でその国の GeoJSON を取得
- fetch の相対 URL は **「そのとき開いているページの URL」** を基準に解決される。
  - 例: `http://localhost:8000/leaflet_map.html` で開いている → `index.json` は `http://localhost:8000/index.json` として要求される。
  - 例: `http://localhost:8000/output_leaflet/leaflet_map.html` で開いている → `index.json` は `http://localhost:8000/output_leaflet/index.json` として要求される。
- サーバを **どのディレクトリで起動したか**／**どの URL で開いたか** で、index.json の「ある場所」と「要求するパス」がずれると、**index.json が見つかりません** になる。

→ 見本は fetch で index.json を読んでいないので問題にならず、今回だけ fetch のパス問題が表に出る。

---

## まとめ

| 項目 | 見本（index_fr.html） | 今回（leaflet_map.html） |
|------|------------------------|---------------------------|
| 国の数 | 1国（フランス） | 193国（プルダウンで選択） |
| データの持ち方 | 1国の GeoJSON を `data_fr.js` に変数として記述 | 国一覧は index.json、各国は別 GeoJSON ファイル |
| 読み込み方法 | **&lt;script src="data_fr.js"&gt;**（fetch なし） | **fetch("index.json")** と **fetch(ファイル名)** |
| index.json | 使っていない | 国一覧用に使用 |
| パスで困る理由 | script の src は HTML の場所基準で取れる | fetch の相対パスは「開いている URL」基準のため、開き方でずれる |

**結論**: 見本では「index.json を fetch しない」＋「1国分だけ script で読み込む」ため問題が出ず、今回のように「複数国で fetch で index.json と GeoJSON を読む」構成だと、**開く URL と index.json の置き場所を一致させる必要**がある。

---

## 対応済み: 見本と同じ方式（data_index.js で一覧を読む）

複数人でどこでも表示できるように、**見本（旧地名地図）と同じ方式**を導入した。

- **build_leaflet_index.py** が **data_index.js** を生成する。
  - 内容: `window.LEAFLET_COUNTRY_INDEX = [ { "file": "...", "label": "...", "cn", "region" }, ... ];`
- **leaflet_map.html** で `<script src="data_index.js"></script>` を読み、国一覧は **window.LEAFLET_COUNTRY_INDEX** を参照する。
- 一覧の取得に **fetch を使わない**ため、開く URL やサーバの起動場所に依存せず、**どこでもプルダウンが表示される**。
- data_index.js が無い場合は従来どおり fetch("index.json") にフォールバックする。
