
# 🧬 Pyowasm

[![GitHub Pages](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-blueviolet?logo=github)](https://dogrun-inc.github.io/pyowasm/)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-%23FF4B4B.svg?logo=streamlit&logoColor=white)
![BioPython](https://img.shields.io/badge/BioPython-3776AB?logo=python&logoColor=white)
![Pyodide](https://img.shields.io/badge/Pyodide-654FF0?logo=webassembly&logoColor=white)
![biowasm](https://img.shields.io/badge/biowasm-00B5C9?logo=webassembly&logoColor=white)
![License](https://img.shields.io/github/license/dogrun-inc/pyowasm)

**Browser-based Bioinformatics Tool with Python + WebAssembly | Python + WebAssembly で動くブラウザバイオインフォマティクスツール**

**公開デモ / Live Demo:** [https://dogrun-inc.github.io/pyowasm/](https://dogrun-inc.github.io/pyowasm/)

## 概要 / Overview

### 日本語

Pyowasm は、Pyodide（ブラウザ Python 実行環境）と WebAssembly を組み合わせ、軽量なバイオインフォマティクス処理を「環境構築なし」で実行できるツールです。CWL や Nextflow のような本格ワークフローの前段として、まず配列解析を試すための高速なプロトタイピング環境を提供します。URL を開くだけで Python ベースの解析を開始できることを重視しています。

**主な機能：**
- **オーソログ解析エンジン**：k-mer インデックス + Jaccard スコア による効率的な候補絞り込み、その後 BioPython の PairwiseAligner による精密な配列アラインメント評価
- **FAA ファイルアップロード対応**：FASTA/FAA ファイルから直接配列を読み込み、テキスト入力と同様に解析
- **配列統計解析**：GC 含有量、k-mer 分布、アミノ酸組成などの統計情報を可視化
- **Wasm ツール統合**：seqtk などの WebAssembly ツールをブラウザ内で実行
- **リアルタイムUI**：Streamlit を用いた対話的なウェブインターフェース

### English

Pyowasm is a browser-based bioinformatics tool that combines Pyodide (Python runtime in the browser) and WebAssembly, enabling lightweight sequence analysis with zero environment setup. Instead of replacing full workflow systems such as CWL or Nextflow, it focuses on rapid experimentation and small-to-medium analyses where heavy setup is a bottleneck. The core experience is: open a URL and start Python-based analysis immediately.

**Key Features:**
- **Ortholog Analysis Engine**: Efficient candidate filtering using k-mer indexing + Jaccard scoring, followed by precise sequence alignment evaluation using BioPython's PairwiseAligner
- **FAA File Upload Support**: Import sequences directly from FASTA/FAA files and analyze them like text input
- **Sequence Statistics**: Visualize GC content, k-mer distribution, amino acid composition, and other statistical metrics
- **WebAssembly Tool Integration**: Execute WebAssembly tools like seqtk directly in browsers
- **Real-time Interactive UI**: Built with Streamlit for an intuitive web interface

---

## インストール / Installation

```bash
pip install .
```

---

## 使い方 / Usage

### ブラウザアプリケーション / Web Application

#### 方法 1: 生成済みの index.html を使用 / Using Pre-generated index.html

通常は、ローカル HTTP サーバーを起動してアクセスしてください：

Use a local HTTP server (recommended):

```bash
# プロジェクトルートで実行
python -m http.server 8000
```

その後、ブラウザで以下にアクセスします：

Then open this URL in your browser:

```text
http://localhost:8000/
```

#### 方法 2: 開発環境での実行 / Running in Development

Python 実装のデバッグ目的で、Streamlit でアプリケーションを実行できます。  
**注意**: 開発環境では以下の制限があります：
- WebAssembly (Wasm) ツールを使用することはできません。
- 解析実行中のローディングオーバーレイ（画面全体のスピナー）は表示されません。

You can run the application with Streamlit for debugging Python implementation.
Note: The following limitations apply in the development environment:
- WebAssembly (Wasm) is not available.
- The loading overlay (full-screen spinner) during analysis will not be displayed.

```bash
# Streamlit アプリケーション起動
streamlit run src/pyowasm/app.py
```

ブラウザが自動的に http://localhost:8501 で立ち上がります。

Your browser will automatically open at http://localhost:8501.

ブラウザが起動しない場合は、手動で [http://localhost:8501](http://localhost:8501) にアクセスしてください。  
If your browser does not open, manually visit [http://localhost:8501](http://localhost:8501).

### index.html の再生成 / Regenerating index.html

ソースコード（Python ファイル）を変更した場合、以下のスクリプトで `index.html` を再生成してください：

When you change the source code (Python files), regenerate `index.html` with the following script:

```bash
python scripts/generate_index.py
```

可読性を優先したい場合は `--pretty` オプションを使用してください：

Use `--pretty` option when you prefer readability in generated JavaScript string blocks:

```bash
python scripts/generate_index.py --pretty
```

**スクリプトの詳細：**

生成スクリプト `scripts/generate_index.py` は、以下の処理を行います：

1. **テンプレート読み込み**: `scripts/template.html` を読み込む
2. **プレースホルダー検査**: `{{PLACEHOLDER:path/to/file.py}}` 形式のプレースホルダーを検出
3. **ファイル埋め込み**: 対応する Python ソースファイルを読み込み、JavaScript 文字列として安全に埋め込む
4. **ファイル出力**: 生成された HTML を `index.html` に保存

**出力モード / Output modes:**

- **デフォルト (安全性優先)**: 1行 JSON 文字列リテラルとして埋め込み（エスケープ破綻を回避）
- **`--pretty` (可読性優先)**: 複数行配列 + `.join("\\n")` 形式で埋め込み

**生成ヘッダー：**

生成された `index.html` には以下のコメントが付与されます（手編集禁止）：
```html
<!-- このファイルは scripts/generate_index.py により自動生成されます。手編集禁止。 -->
```

**例：**

```bash
# 開発中に複数回実行する場合
python scripts/generate_index.py  # OK 生成完了: C:\git\pyowasm\index.html
```

---

## テスト / Testing

```bash
pytest tests/
```

すべてのユニットテストが通過することを確認してください。

Ensure all unit tests pass.

---

## ライセンス / License

MIT License

---

## 開発者 / Developer

Developed by [Dogrun Inc.](https://dogrun.jp/) | [GitHub](https://github.com/dogrun-inc/)
