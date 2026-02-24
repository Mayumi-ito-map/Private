### なぜ `sum()` より `extend()` の方が良いのか？

#### ① `sum(list_of_lists, [])` が良くない理由

例：

```python
texts = sum(
    [replace_abbreviation_with_dict(t, abbreviation_dict) for t in texts],
    []
)
```

一見シンプルに見えるが、内部では以下のように動く：
```
[] + list1 → 新しいlist作成
その結果 + list2 → また新しいlist作成
その結果 + list3 → また新しいlist作成
…
```
つまり、毎回リストをコピーし直している。  
リストが増えるたびに全コピーが毎回発生する
計算量
```
O(n²)
```
データが増えると急に遅くなる。

#### ② extend() を使う場合
```
expanded_texts = []
for t in texts:
    expanded_texts.extend(
        replace_abbreviation_with_dict(t, abbreviation_dict)
    )
```
extend() は：
既存のlistの**末尾**に要素を追加するだけ  
新しいリストを毎回作らない。

計算量
```
O(n)
```
大規模データでも安定。

#### ③ Python公式の考え方
Python公式ドキュメントでも：
sum() は**数値計算用**であり、**リスト結合には推奨されない**  
とされている。

#### ④ 可読性の違い
sum版
```
sum([...], [])
```
flattenしていることが直感的に分かりにくい

extend版
```
expanded_texts = []
for ...
    expanded_texts.extend(...)
```

* 「展開している」ことが明確
* 処理意図が読み取りやすい

