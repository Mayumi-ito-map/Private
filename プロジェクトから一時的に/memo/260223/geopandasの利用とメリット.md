# geopandas の利用とメリット

## このプロジェクトでの使用状況

| スクリプト | geopandas 使用 |
|------------|----------------|
| **geonames_loader.py** | ✅ 使用している。`records_to_gdf()` で地名レコードを GeoDataFrame に変換し、`get_geonames_for_country()` の返り値の一つとして返す。 |
| **run_stage_match_quote_variants.py** | 受け取るが未使用。`placename_dict, records, gdf = get_geonames_for_country(...)` のうち `records` と `placename_dict` のみ利用。 |
| **run_local_build.py** | 同上。`gdf` は未使用。 |
| **build_geojson_leaflet.py** | ❌ 使用していない。辞書とリストで GeoJSON を組み立て、`json.dump` で出力。 |
| **export_for_leaflet.py** | ❌ 使用していない。同上。 |

→ **ここまでのスクリプトでは、GeoJSON 生成（build_geojson_leaflet / export_for_leaflet）では geopandas は使っていません。**  
geonames_loader では「距離・地図用」として GeoDataFrame を返しているが、現状の司令塔①②では参照されていません。

---

## geopandas のメリット

- **地理空間の「表」として扱える**  
  pandas の DataFrame に `geometry` 列（Point, LineString, Polygon 等）が乗った形。行＝地点・区域として、属性とジオメトリを一括で扱える。
- **空間演算がそのまま使える**  
  距離・バッファ・交差・包含・重なりなどがメソッドや関数で用意されている（shapely + 空間インデックス）。
- **CRS（座標系）の管理**  
  緯度経度（EPSG:4326）とメートル系（UTM 等）の変換、`to_crs()` で統一できる。
- **入出力が豊富**  
  Shapefile, GeoJSON, GeoPackage などの読み書きが `gpd.read_file()` / `to_file()` でできる。GeoJSON も `gdf.to_file("x.geojson", driver="GeoJSON")` で出せる。

---

## どういう場合に使うか

- **「どの地点がどの範囲に含まれるか」を判定したい**  
  例: 緯度経度の点が、国境ポリゴンやメッシュのどの区域に落ちるか。
- **「近くの N 件」を求めたい**  
  例: ある地点から半径 10 km 以内の地名、または距離でソートした上位 5 件。
- **距離・面積を正確に計算したい**  
  例: ローカル地点と GeoNames 候補の距離（km）。haversine の代わりに `gdf.geometry.distance()` や投影後の距離を使える。
- **複数レイヤーを重ねて処理したい**  
  例: 地名ポイントと行政境界ポリゴンを結合・クリップする。
- **既存の GIS データ（Shapefile / GeoPackage）と結合したい**  
  読み込み・属性結合・フィルタを pandas 感覚でできる。

---

## 地名データベースで一般的に使う場合

- **候補点と参照データの空間結合**  
  例: ローカル地名の座標を「どの県・市に属するか」で付与する（ポリゴンとの contain）。
- **近傍検索・距離順ランキング**  
  例: ある地名から最も近い GeoNames 候補を距離でソートして表示。
- **重複・近接の検出**  
  例: 同一またはごく近い位置の候補をマージしたり、閾値以内の点をグルーピングする。
- **可視化・レポート**  
  例: GeoDataFrame をそのまま `.explore()` で簡易地図化、または GeoJSON/Shapefile に書き出して QGIS や Leaflet に渡す。

---

## このプロジェクトで geopandas を使うなら

- **距離計算の共通化**  
  現在は `export_for_leaflet.py` で haversine を自前実装。GeoDataFrame にすれば `distance()` や `sjoin_nearest` で「最も近い候補」を統一実装できる。
- **GeoJSON 出力の一本化**  
  `build_geojson_leaflet.py` で dict を組み立てる代わりに、Local / GeoNames をそれぞれ GeoDataFrame 化してから `pd.concat` し、`to_file(..., driver="GeoJSON")` で出す方法もある（CRS や property 名の制御は必要）。
- **「候補がどの行政区画に属するか」の付与**  
  国・州・県のポリゴンがあれば、地名ポイントをそれらと空間結合し、属性として付与できる。

現状は「名前のマッチング」が主で、空間クエリや距離ランキングをあまり使っていないため、**必須ではないが、距離・範囲・ポリゴンを使う処理を増やすなら導入の価値が高い**、という位置づけです。
