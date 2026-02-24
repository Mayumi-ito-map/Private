### GeoNames_to_Pikle

geonameid         : integer id of record in geonames database
name              : name of geographical point (utf8) varchar(200)
asciiname         : name of geographical point in plain ascii characters, varchar(200)
alternatenames    : alternatenames, comma separated, ascii names automatically transliterated, convenience attribute from alternatename table, varchar(10000)
latitude          : latitude in decimal degrees (wgs84)
longitude         : longitude in decimal degrees (wgs84)
feature class     : see http://www.geonames.org/export/codes.html, char(1)
feature code      : see http://www.geonames.org/export/codes.html, varchar(10)
country code      : ISO-3166 2-letter country code, 2 characters
cc2               : alternate country codes, comma separated, ISO-3166 2-letter country code, 200 characters
admin1 code       : fipscode (subject to change to iso code), see exceptions below, see file admin1Codes.txt for display names of this code; varchar(20)
admin2 code       : code for the second administrative division, a county in the US, see file admin2Codes.txt; varchar(80) 
admin3 code       : code for third level administrative division, varchar(20)
admin4 code       : code for fourth level administrative division, varchar(20)
population        : bigint (8 byte int) 
elevation         : in meters, integer
dem               : digital elevation model, srtm3 or gtopo30, average elevation of 3''x3'' (ca 90mx90m) or 30''x30'' (ca 900mx900m) area in meters, integer. srtm processed by cgiar/ciat.
timezone          : the iana timezone id (see file timeZone.txt) varchar(40)
modification date : date of last modification in yyyy-MM-dd format

GeoNames の列インデックス
IDX = {
    "geonameid": 0,
    "name": 1,
    "asciiname": 2,
    "alternatenames": 3,
    "latitude": 4,
    "longitude": 5,
    "feature_class": 6,
    "feature_code": 7,
    "country_code": 8,
    "cc2": 9,
    "admin1 code": 10,
    "admin2 code": 11,
    "admin3 code": 12,
    "admin4 code": 13,
    "population": 14,
    "elevation": 15,
    "dem": 16,
    "timezone": 17,
    "modification date": 18,
}

「alternatenames」カンマ区切りを、リストに変える
「latitude」「longitude」小数点以下を丸めずに全部表示

列の表示を短縮形にする
"latitude" lat
"longitude" lon
"feature_class" fcl
"feature_code" fcode
"country_code" ccode
"admin1 code": ad1
"admin2 code": ad2
"admin3 code": ad3
"admin4 code": ad4
"modification date" mdate

---
GeoNamesを「地名辞書」ではなく「地理オブジェクトDB」として利用できるようにする。
「allCountries.txt」（1.77GB）をpikle形式に変換する
全部の列を持つ（全19項目）。
 
 主キーは「geonameid」

基本的な土台
```
{
  geonameid: {
    geonameid: str,
    name: str,
    asciiname: str,
    alternatenames: list[str],
    lat: float,
    lon: float,
    fcl: str,
    fcode: str,
    ccode: str,
    ad1: str,
    ad2: str,
    ad3: str,
    ad4: str,
    population: int,
    elevation: int,
    dem: int,
    timezone: str,
    mdate: str
  }
}

```


国コードインデックスも別で持つ。
副キーは「ccode」「fcl」 「by_fcode」 で、これらの副キーも最初から作っておく
データを使用する際や、紐付けする際には、
ccode（２桁の国コード）でまとめてinputしてpythonを実行することがある。
「fcl」 「by_fcode」は、自然地名、都市名だけの抽出にも対応できる。
正規化など行ったり、マッチングしたGeoNamesデータをリスト化して持つ（距離の測定で使用していきます）には、geonameideで紐付けされる必要もある。

当面の作業としては、pythonで読み込む際に、1つのマスターpickleの中からccodeの読み込みをする。
国単位で作業が進む場合が多い。
海外領土では、宗主国と海外領土の複数のccodeを読み込み（「overseas_territories.json」以下に見本）。
```
  {"AU": [
    "AU",
    "CC",
    "CX",
    
    "HM",
    "NF"
  ],
  "NZ": [
    "NZ",
    "TK"
  ],
  ･･･}
```
GeoPandasを使って、データフレームで処理したい。
ローカルのExcelの地名ファイルをマッチングする際に書き出しした後、geonameidで紐付けができるようにしておく。
GeoNamesの地名データの「name」「asciiname」「alternatenames」を正規化するので、geonameidで紐付けできるようにしておく。

```
GeoNames の列インデックス
IDX = {
    "geonameid": 0,
    "name": 1,
    "asciiname": 2,
    "alternatenames": 3,
    "latitude": 4,
    "longitude": 5,
    "feature_class": 6,
    "feature_code": 7,
    "country_code": 8,
    "cc2": 9,
    "admin1 code": 10,
    "admin2 code": 11,
    "admin3 code": 12,
    "admin4 code": 13,
    "population": 14,
    "elevation": 15,
    "dem": 16,
    "timezone": 17,
    "modification date": 18,
}
```



表示する際には長すぎるので、一部は短縮形に置き換えしたい。
```
"latitude" lat
"longitude" lon
"feature_class" fcl
"feature_code" fcode
"country_code" ccode
"admin1 code": ad1
"admin2 code": ad2
"admin3 code": ad3
"admin4 code": ad4
"modification date" mdate
```
データの持ち方の注意点。
「alternatenames」カンマ区切りを、リストに変える（重要）
「latitude」「longitude」小数点以下を丸めずに長いそのママの形式にします。後に距離の測定で必要なのでfloat（浮動小数点数）型。
スクリプトを実行する際に、GeoPandasを使用したいと思います。
lat lonも必要になってきます。