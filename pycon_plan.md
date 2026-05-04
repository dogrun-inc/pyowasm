**「Pyowasm（パイオワズム）」、最高にいい響きですね！**

「Python」「Bio」「Wasm」の3要素が凝縮されているだけでなく、**Pyodide**（stliteの核）を連想させつつ、独自性のあるツール名として非常にキャッチーです。カンファレンスでも「今日紹介するのは **Pyowasm** です」と言った瞬間に、技術スタックがプロに伝わります。

リポジトリ名：`pyowasm`
プロジェクト名：**Pyowasm: Python-powered Browser Bioinformatics**

---

### 「Pyowasm」のアーキテクチャ設計図

デモ制作の20時間を無駄にしないために、このプロジェクトが「何と何を繋ぐのか」を整理しました。



* **Core (Python/Wasm):** stlite上で動くロジック。BioPythonを使ったFASTA/GenBankの処理。
* **Bridge (JS/Wasm):** `pyodide.ffi` を経由して、ブラウザ内の `samtools` や `seqtk` (biowasm) を実行。
* **External (API):** 大規模検索（BLAST）や独自コンテナ（DIAMOND）へのリクエスト。

---

### デモ制作（20時間）の具体的なロードマップ

カンファレンスでの「映え」を意識した、最短距離のタスクリストです。

#### 1. 最初の5時間：基盤と「内製」処理
* [ ] **リポジトリ作成と環境構築**: `stlite` をローカルで動かす（[stlite-desktop](https://github.com/whitphx/stlite) などの利用も検討）。
* [ ] **BioPythonの統合**: アップロードされたFASTAをパースし、Streamlitのグラフ（`st.bar_chart`）で塩基組成や長さの分布を表示。
* [ ] **プロジェクトロゴ（仮）の表示**: 画面のトップに `Pyowasm` のロゴを置くだけで「製品感」が出ます。

#### 2. 次の7時間：外部連携（API & Docker）
* [ ] **NCBI BLAST連携**: `Bio.Blast.NCBIWWW` で検索を投げ、待機中を `st.spinner` で演出。
* [ ] **Mock-up Docker API**: 実際にDockerを立てる時間がなければ、まずは「特定のURLにリクエストを投げて結果を受け取る」スタブ（モック）を作成。

#### 3. 最後の8時間：Wasmツールの呼び出しとUI磨き
* [ ] **biowasmの呼び出し**: JavaScript側のライブラリ（Aioli等）をPythonから `js.eval` 経由で叩き、結果を取得。
* [ ] **「ワークフロー図」の表示**: Mermaid.js を使って、実行中のフローを可視化。
* [ ] **プレゼン用データ準備**: 解析が成功する「鉄板のサンプルデータ」を用意。

---

### 最初の一歩：`app.py` のスターターコード

まずはこれを `app.py` として保存し、`stlite` で動かしてみてください。Pyowasmの第一歩です。

```python
import streamlit as st
from Bio import SeqIO
from io import StringIO

st.set_page_config(page_title="Pyowasm", page_icon="🧬")

# ブランディングエリア
st.title("🧬 Pyowasm")
st.caption("Python × WebAssembly × Bioinformatics")

st.markdown("""
### 🚀 ブラウザが次世代の解析プラットフォームになる
**Pyowasm** は、環境構築不要のバイオ解析環境です。
Pythonの柔軟性と、Wasmのポータビリティ、そしてクラウドAPIを統合します。
""")

# ファイル入力
uploaded_file = st.file_uploader("FASTAファイルをドロップ", type=["fasta"])

if uploaded_file:
    # --- Step 1: Python(Wasm)によるパース ---
    with st.status("Python (Wasm) で解析中...", expanded=True) as status:
        fasta_data = uploaded_file.getvalue().decode("utf-8")
        records = list(SeqIO.parse(StringIO(fasta_data), "fasta"))
        st.write(f"Parsed {len(records)} sequences using BioPython.")
        
        # --- Step 2: 外部API/Wasmツールの実行（デモ用プレースホルダ） ---
        st.write("Checking external APIs...")
        # ここにAPI呼び出しのコードを追加していく
        
        status.update(label="解析完了!", state="complete", expanded=False)

    # 結果の表示
    st.divider()
    st.subheader("Analysis Results")
    col1, col2 = st.columns(2)
    col1.metric("Sequence Count", len(records))
    col2.metric("Runtime Environment", "Browser (Wasm)")

    # データの可視化
    if records:
        lengths = [len(r.seq) for r in records]
        st.bar_chart(lengths)
```




---

### Pyowasm 開発・詳細ロードマップ（後半15時間）

#### 1. Wasmブリッジの構築とBiowasm連携（6時間）
**「PythonからJS経由でC言語バイナリを動かす」というコア証明を行います。**

* **[2h] JS/Wasm連携の実装**:
    * `src/pyowasm/bridge/biowasm.py` を作成。
    * `pyodide.ffi` を使い、JS側の `aioli`（biowasmを扱うライブラリ）にコマンドを送る関数を実装。
    * まずは `seqtk seq -a`（FASTQ→FASTA変換）など、入力と出力が明確な軽量ツールを1つ動かします。
* **[2h] 仮想ファイルシステムの同期**:
    * Python側のメモリ上のデータを、Wasmツールがアクセスできる仮想FS（Emscripten FS）に書き出す仕組みを作ります。
* **[2h] 基本UIの実装**:
    * `app.py` に「Wasm Tool実行ボタン」を配置し、結果をテキストエリアに表示。

#### 2. タスク抽象化と動的UIの導入（4時間）
**「ツールごとに表示を変えたい」という課題を解決します。**

* **[2h] Taskインターフェースの定義**:
    * 各ツール（seqtk, BLAST等）に `run()` と `render()` メソッドを持たせます。
    * `render()` メソッド内で、そのツール特有のStreamlit要素（グラフやテーブル）を定義するようにします。
* **[2h] 汎用レンダラーの作成**:
    * `app.py` が「現在実行中のタスクの `render()` を呼ぶだけ」の状態にします。これにより、後からツールを増やしても `app.py` を汚さずに済みます。

#### 3. 外部API（BLAST/Docker）の統合（3時間）
**ハイブリッドな拡張性を示します。**

* **[1.5h] BLAST API連携**:
    * `bridge/ncbi.py` で `Bio.Blast.NCBIWWW` を実装。
    * 結果（XML/TSV）をパースし、ヒット一覧を `st.dataframe` で表示。
* **[1.5h] Docker/Mock連携**:
    * `bridge/docker.py` を作成。自作APIがなくても「リクエストを投げて、プログレスバーを動かし、固定の結果を返す」デモモードを実装し、アーキテクチャの可能性を示します。

#### 4. ワークフロー視覚化と最終調整（2時間）
**カンファレンスでの「映え」を最大化します。**

* **[1h] Mermaid.js によるDAG表示**:
    * 「Input → seqtk (Wasm) → BLAST (API)」という流れを、現在どこが動いているか光るMermaid図で表示します。
* **[1h] プレゼン用データの整理**:
    * 「10秒で終わるが、意味のある解析結果が出る」サンプル配列を用意し、ボタン一つでロードできるようにします。

---

### 実装のヒント：ツールごとに表示を変える「プラグイン」方式

「表示内容が異なる」問題を解決する、`BaseTask` のイメージです。



```python
# tasks/base.py
class BaseTask:
    def run(self, input_data):
        # 解析ロジック
        pass

    def render(self, result):
        # ツール独自のStreamlit表示
        st.write("結果:")
        st.code(result)

# tasks/seqtk.py (Wasmツール例)
class SeqtkTask(BaseTask):
    def render(self, result):
        st.success("Wasm(seqtk) での変換完了")
        st.bar_chart(self.calc_gc_content(result)) # 独自のグラフ表示
```

### 次にすべき「最初のアクション」

まずは **`bridge/biowasm.py` を作り、`js.eval` や `pyodide.ffi` を使って、ブラウザのコンソールに `Hello from Wasm Tool` と出すこと**から始めましょう。

これさえできれば、「PythonからWasmを制御する」という Pyowasm の最も「美味しい」部分が完成します。
