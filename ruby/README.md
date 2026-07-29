# Ruby.WASM 版 pyowasm (ortholog only)

このディレクトリでは、Ruby.WASM 上で動作するオーソログ解析ページを提供します。

## 使い方

1. ローカル HTTP サーバーを起動します。
   ```bash
   python -m http.server 8000
   ```
2. ブラウザで [http://localhost:8000/ruby/](http://localhost:8000/ruby/) を開きます。
3. Species A / B の FASTA 文字列を入力し、解析ボタンを押します。

## 実装ポイント

- RBH の前処理・候補選定・結果整形は Ruby で実装しています。
- 画面表示は Ruby 側で ERB 文字列を生成しています。
- アラインメントは pycall-lite 経由で Biopython を利用し、結果表は pandas で整形します。
