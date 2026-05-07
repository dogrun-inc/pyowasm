# index.html 生成スクリプト 設計ドキュメント

## 目的

`src/pyowasm/` 配下の Python 実装ファイルを唯一の正として、
ブラウザ上で動作する stlite 版 `index.html` を自動生成する。

手動で `dev.html` と `src/` を二重メンテする作業をなくし、
`src/` を更新したら `python scripts/generate_index.py` を実行するだけで
`index.html` を最新化できる状態を目指す。

## ファイル構成

```
scripts/
  DESIGN.md           # 本ドキュメント
  template.html       # index.html のひな形（プレースホルダー入り）
  generate_index.py   # 生成スクリプト本体
index.html            # 生成物（手編集禁止）
dev.html              # 開発時動作確認用（手編集可・生成対象外）
```

## テンプレートのプレースホルダー形式

```
{{PLACEHOLDER:相対パス}}
```

例:
```js
const schemaCode = {{PLACEHOLDER:src/pyowasm/models/schema.py}};
```

生成スクリプトがこのパターンを検出し、対応する Python ファイルの内容に置換する。

## String.raw テンプレートリテラルとバッククォート問題

JavaScript の `String.raw\`...\`` はバッククォート文字をそのまま含めることができない。
Python ソースコード中にバッククォート（`` ` ``）が含まれる場合、生成スクリプトは
バッククォートで分割して結合式を生成する。

**変換例（バッククォートが1箇所の場合）:**
```js
// 入力ファイル内容: "VFS内のファイルを処理します: `{input_filename}`"
// 生成結果:
String.raw`...VFS内のファイルを処理します: ` + "`" + String.raw`{input_filename}` + "`" + String.raw`...`
```

## 生成スクリプトの処理フロー

1. `scripts/template.html` を読み込む
2. `{{PLACEHOLDER:path}}` パターンをすべて検出する
3. 各 `path` の Python ファイルを読み込む
4. バッククォートが含まれる場合は分割結合式に変換する
5. プレースホルダーを変換済みの JS 式で置換する
6. リポジトリルートの `index.html` として出力する

## index.html の管理方針

- 生成物であることを示すコメントをファイル先頭に挿入する
- `.gitignore` には含めず、生成後の `index.html` をコミット管理する
  （理由: GitHub Pages 等へのデプロイに必要なため）
- CI での自動チェック（任意）: `generate_index.py` 実行後に差分がなければ OK

## dev.html との関係

| 項目 | dev.html | index.html |
|------|----------|------------|
| 用途 | 開発時動作確認 | 本番デプロイ用 |
| 管理 | 手動編集可 | 手編集禁止（生成物） |
| Python コード | 直接埋め込み | src/ から自動生成 |
| タイトル | Pyowasm Dev Preview | Pyowasm |
| 更新方法 | 直接編集 | generate_index.py 実行 |
