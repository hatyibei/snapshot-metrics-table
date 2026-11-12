# snapshot-metrics-table

記事メトリクスの CSV（複数時点のスナップショット）を読み、記事ごとの likes / pv の推移を表にして標準出力に出す小さな CLI ツールです。Python 3 の標準ライブラリだけで動きます。

> **English summary:** A tiny, dependency-free Python CLI that reads a CSV of article metric snapshots (`initial` / `24h` / `7d`) and prints a per-article table of likes and page views to stdout.
>
> ```sh
> python3 metrics_table.py examples/sample_metrics.csv
> ```

## 必要なもの

- Python 3.7 以上（追加パッケージ不要）

## 使い方

```sh
python3 metrics_table.py <CSVのパス>
```

サンプルで試す:

```sh
python3 metrics_table.py examples/sample_metrics.csv
```

出力例（警告は標準エラー出力）:

```text
警告: 不明な snapshot_type 'weekly' を無視しました (https://example.com/posts/sample-b)
platform | title                                        | initial likes | 24h likes | 7d likes | 7d pv
---------+----------------------------------------------+---------------+-----------+----------+------
blog     | 架空の記事A：小さなCLIツールを整える手順メモ |             3 |        12 |       21 |   430
wiki     | Fictional Post B: notes on CSV               |             1 |         5 |        - |     -
blog     | 架空の記事C（公開日不明のテスト用）          |             0 |         - |        - |     -
```

### 終了コード

| コード | 意味 |
| --- | --- |
| 0 | 正常終了 |
| 1 | CSV を開けない（存在しない、ディレクトリを指定した など） |
| 2 | 引数の数が正しくない |

## 入力 CSV の列

1 行目はヘッダー行です。UTF-8（BOM 付きも可）で読みます。

| 列 | 使い方 |
| --- | --- |
| `snapshot_at` | スナップショットを取った日時（ISO 8601。`Z` や `+09:00` 可。タイムゾーンなしは UTC 扱い） |
| `snapshot_type` | `initial` / `24h` / `7d` のいずれか |
| `url` | 記事の識別キー。空の行は無視 |
| `platform` | 掲載先の名前（出力の `platform` 列） |
| `title` | 記事タイトル |
| `theme` | 読み込むが出力には使わない |
| `published_at` | 公開日時（ISO 8601）。並び順に使う |
| `likes` | いいね数 |
| `stocks_or_bookmarks` | 読み込むが出力には使わない |
| `pv` | ページビュー |
| `comments` | 読み込むが出力には使わない |

## 出力列

| 列 | 内容 |
| --- | --- |
| `platform` | 掲載先 |
| `title` | タイトルの空白を 1 つに畳んだうえで先頭 30 文字 |
| `initial likes` | `initial` スナップショットの likes |
| `24h likes` | `24h` スナップショットの likes |
| `7d likes` | `7d` スナップショットの likes |
| `7d pv` | `7d` スナップショットの pv |

- 並び順は `published_at` の新しい順。読めない・空の日時の記事は末尾。
- 全角文字（東アジア幅 W/F）は 2 桁として数えるので、日本語タイトルでも列が揃います。

## 欠損・重複行の扱い

- **欠損**: 値が空、またはそのスナップショット自体がない場合は `-` を表示します。
- **重複**: 同じ `url`・同じ `snapshot_type` の行が複数あるときは、`snapshot_at` が最も新しい行を使います。
  - `Z` と `+09:00` などは同じ時刻軸に直して比較します。
  - `snapshot_at` が空・読めない行より、日時がある行を優先します。
  - 同じ日時なら後に出てきた行を使います。
- **不明な `snapshot_type`**: 標準エラー出力に警告を出して、その行の数値は無視します。
- **`url` が空の行**: 黙って無視します。
- `platform` / `title` / `published_at` は、その `url` で最初に出てきた空でない値を使います。

## テスト

```sh
python3 -m unittest
```

`tests/` に unittest のテストがあります（pytest は不要）。テストデータはすべて架空です。

## ライセンス

[MIT](LICENSE) © 2026 hatyibei
