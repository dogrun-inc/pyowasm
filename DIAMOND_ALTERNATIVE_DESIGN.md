# DIAMOND 代替設計（k-mer 候補絞り込み + RBH）

## 1. 背景

当初の Wasm ベース smith_waterman 経路（seq-align 経由）は、大規模なタンパク質配列集合に対して安定性に課題がありました。
確認された問題:
- 出力形式の不一致によりスコア解析が安定しない
- memory access out of bounds などの実行時エラー

ブラウザ内で DIAMOND 的な高速探索挙動を代替するため、精密スコアリング前に比較対象を削減する純 Python パイプラインを実装しました。

## 2. 目的

タンパク質オーソログ探索向けの実用的な Reciprocal Best Hit（RBH）ワークフローを構築すること:
- Pyodide/stlite 環境で動作する
- 可能な限り N x M の全ペア精密アラインメントを避ける
- 候補を絞った上で厳密アラインメントを行い、最終選択品質を維持する

## 3. 適用範囲

実装対象:
- src/pyowasm/tasks/wasm/ortholog_analyzer.py
- src/pyowasm/ui/components.py
- dev.html（埋め込み同期）

対象外:
- 外部ネイティブバイナリ（DIAMOND、BLAST+、MMseqs2）
- マルチプロセス / スレッド並列による高速化

## 4. 全体アーキテクチャ

Step 1: 入力正規化とフィルタリング
- FASTA の BOM 除去
- 配列を大文字へ正規化
- BLOSUM62 非対応文字を含むレコードの除外
- description に対する任意キーワード抽出

Step 2: k-mer インデックスによる高速候補生成
- subject 側の k-mer 逆引きインデックスを構築
- 各 query について共有 k-mer を持つ subject 候補を収集
- Jaccard スコアで粗い類似度を算出
- query ごとに上位 top_n 候補のみ残す

Step 3: 候補に限定した精密スコアリング
- PairwiseAligner（BLOSUM62、open=-11、extend=-1）を利用
- アラインメントスコア（bitscore）最大の subject を採用
- identity は min(best_score / self_score * 100, 100) で近似

Step 4: Reciprocal Best Hit（RBH）結合
- A -> B、B -> A の best-hit テーブルを作成
- 相互関係で merge
- 前方向 / 逆方向の identity・bitscore を持つ RBH テーブルを出力

## 5. 主要データ構造

- k-mer インデックス:
  - 型: dict[str, set[str]]
  - 意味: k-mer -> その k-mer を含む subject 配列 ID 集合

- subject k-mer キャッシュ:
  - 型: dict[str, set[str]]
  - 意味: subject ID -> 一意 k-mer 集合

- best-hit テーブル行スキーマ:
  - query: str
  - subject: str
  - identity: float
  - bitscore: float

- 最終 RBH 行スキーマ:
  - query_a, query_b
  - identity_a_to_b, identity_b_to_a
  - bitscore_a_to_b, bitscore_b_to_a

## 6. 公開パラメータ

- k（デフォルト 4）
  - UI 範囲: 3 から 6
  - k を大きくすると特異性は上がるが、再現率が下がる場合がある

- top_n（デフォルト 20）
  - UI 範囲: 5 から 100
  - 精密アラインメント段階の精度・処理時間トレードオフを制御

## 7. 実装メソッド

OrthologAnalysisTask 内:
- _build_kmer_index(seqs, k=4)
- _get_candidates(query_record, subject_index, subject_kmer_sets, top_n=20, k=4)
- _compute_best_hits_fast(seqs_query, seqs_subject, k=4, top_n=20)
- run(sample_a, sample_b, keywords_a=None, keywords_b=None, k=4, top_n=20)

メイン経路から削除した要素:
- _parse_smith_waterman_output
- _search_seq_align
- _compute_best_hits（全組合せフォールバック）
- UI の allow_fallback 制御

## 8. 計算量と性能モデル

定義:
- Q = query 配列数
- S = subject 配列数
- C = query あたりの平均選択候補数（概ね top_n）

従来（全組合せ）:
- 精密アラインメント回数: Q x S

現行（候補絞り込み）:
- 精密アラインメント回数: おおむね Q x C
- これに軽量な k-mer インデックス構築・集合演算が加わる

想定ワークロード例:
- Q=883、S=160、top_n=20
- 全組合せ: 141,280 回
- 絞り込み後: 約 17,660 回

## 9. 障害時ハンドリング

- ある query で共有 k-mer が 0 件の場合、その query に限り全 subject を対象に精密アラインメントを実施
- いずれか一方向で best-hit テーブルが空なら、警告付きで空 RBH を返す
- 相互結合結果が空なら、警告付きで空 RBH を返す

## 10. UI と開発体験

オーソログモードの UI 変更:
- Wasm フォールバックチェックボックスを廃止
- k スライダーと top_n スライダーを追加
- ステータス文言を汎用 RBH 解析向けに更新

開発者向け可視性:
- 警告メッセージに、精密アラインメント実行回数と全組合せ回数を出力

## 11. ブラウザ制約下で DIAMOND 代替と呼べる理由

本設計は、高速ホモロジー探索ツールで一般的な 2 段階アプローチを模倣しています:
- 粗い事前絞り込み（k-mer 類似度）
- 小さい候補集合に対する厳密スコアリング

DIAMOND と機能同等ではありませんが、ネイティブ実行ファイルが利用できない環境における対話的 RBH 解析として、実用的な近似解を提供します。

## 12. 今後の改善案

- query 長や k-mer エントロピーに基づく適応的 top_n
- 2 次粗スコア（希少 k-mer 共有重み付け）の任意導入
- 候補スコア計算のバッチベクトル化（NumPy）
- subject 側 k-mer インデックスの実行間キャッシュ
- 系統群に応じた置換行列の切替オプション
